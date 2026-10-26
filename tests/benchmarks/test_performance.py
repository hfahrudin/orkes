"""Performance regression tests for the graph runner.

Unlike the LangGraph comparison scripts next to this file, these are pass/fail
checks meant to catch orkes getting slower or leaking memory.

Time limits are ratios against a reference measured on the same machine in
the same test (e.g. "orkes overhead vs. calling the node functions directly"),
so they hold on fast and slow machines alike. Each timing takes the best of
several repeats to reduce noise.

Run with:  pytest tests/benchmarks -m perf -s   (-s prints the measured numbers)
"""
import asyncio
import copy
import gc
import subprocess
import sys
import time
import tracemalloc
from typing import TypedDict

import pytest

from orkes.graph.core import OrkesGraph
from orkes.graph.utils import orkes_tracable

pytestmark = pytest.mark.perf

NUM_NODES = 10


class S(TypedDict):
    n: int
    data: dict


def _step(s: S):
    s["n"] += 1
    return s


def _chain_graph(traced: bool) -> OrkesGraph:
    """START -> node_0 -> ... -> node_9 -> END."""
    g = OrkesGraph(S, traced=traced)
    names = [f"node_{i}" for i in range(NUM_NODES)]
    for name in names:
        g.add_node(name, _step)
    g.add_edge(g.START, names[0])
    for a, b in zip(names, names[1:]):
        g.add_edge(a, b)
    g.add_edge(names[-1], g.END)
    return g


def _loop_graph(passes: int, traced: bool) -> OrkesGraph:
    """START -> loop (runs `passes` times) -> END."""
    def gate(s: S):
        return "again" if s["n"] < passes else "done"

    g = OrkesGraph(S, traced=traced)
    g.add_node("loop", _step)
    g.add_edge(g.START, "loop")
    g.add_conditional_edge("loop", gate, {"again": "loop", "done": "END"}, max_passes=passes + 1)
    return g


def _best_time(fn, repeats: int = 7, number: int = 1) -> float:
    """Best per-call time in seconds over `repeats` batches of `number` calls."""
    best = float("inf")
    for _ in range(repeats):
        start = time.perf_counter()
        for _ in range(number):
            fn()
        best = min(best, (time.perf_counter() - start) / number)
    return best


def _big_data(size: int = 50_000) -> dict:
    return {f"key_{i}": f"value_{i}" for i in range(size)}


def _report(label: str, value: float, limit: float) -> None:
    print(f"\n  {label}: {value:.2f} (limit {limit})")


# --- Runner overhead ----------------------------------------------------------

def _direct_calls():
    """Reference: the same work as the chain graph, without orkes."""
    s = {"n": 0, "data": {}}
    for _ in range(NUM_NODES):
        s = _step(s)
    return s


@pytest.mark.parametrize("traced, limit", [(False, 40), (True, 200)])
def test_runner_overhead_vs_direct_calls(traced, limit):
    """Running a 10-node chain should cost a bounded multiple of calling the
    10 functions directly. Catches extra work added per edge."""
    runner = _chain_graph(traced).compile()
    orkes_time = _best_time(lambda: runner.run({"n": 0, "data": {}}), number=200)
    direct_time = _best_time(_direct_calls, number=200)

    ratio = orkes_time / direct_time
    _report(f"traced={traced} overhead ratio", ratio, limit)
    assert ratio < limit


# --- State size ---------------------------------------------------------------

def test_untraced_run_time_does_not_grow_with_state_size():
    """Untraced runs must never copy the whole state per edge, so a 50k-entry
    state should run about as fast as an empty one."""
    runner = _chain_graph(traced=False).compile()
    big = _big_data()
    small_time = _best_time(lambda: runner.run({"n": 0, "data": {}}), number=50)
    big_time = _best_time(lambda: runner.run({"n": 0, "data": big}), number=50)

    ratio = big_time / small_time
    limit = 3
    _report("untraced big/small state ratio", ratio, limit)
    assert ratio < limit


def test_traced_snapshot_cost_is_one_copy_per_edge():
    """Traced runs deep-copy the state once per edge for snapshots. The run
    should cost about that much, not more (e.g. an accidental second copy)."""
    runner = _chain_graph(traced=True).compile()
    state = {"n": 0, "data": _big_data()}
    edges = NUM_NODES + 1

    run_time = _best_time(lambda: runner.run(state), repeats=5)
    copies_time = _best_time(lambda: copy.deepcopy(state), repeats=5) * edges

    ratio = run_time / copies_time
    limit = 1.8
    _report("traced run / (one deepcopy per edge) ratio", ratio, limit)
    assert ratio < limit


# --- Scaling ------------------------------------------------------------------

@pytest.mark.parametrize("traced", [False, True])
def test_loop_time_scales_linearly_with_passes(traced):
    """Doubling loop passes should about double run time. Catches work that
    grows with run length (e.g. scanning the whole trace on every edge)."""
    short = _loop_graph(1000, traced).compile()
    long = _loop_graph(4000, traced).compile()
    short_time = _best_time(lambda: short.run({"n": 0, "data": {}}), repeats=5)
    long_time = _best_time(lambda: long.run({"n": 0, "data": {}}), repeats=5)

    ratio = long_time / short_time  # 4x the passes; linear would be ~4
    limit = 6
    _report(f"traced={traced} 4000/1000-pass time ratio", ratio, limit)
    assert ratio < limit


# --- Memory -------------------------------------------------------------------

@orkes_tracable
def _traced_helper(x):
    return x


def _step_with_function_trace(s: S):
    _traced_helper(s["n"])
    s["n"] += 1
    return s


def test_repeated_runs_do_not_leak_memory():
    """Memory must stay flat across many runs on one compiled graph. Catches
    trace data that outlives its run (e.g. lists shared between runs)."""
    g = OrkesGraph(S)
    g.add_node("a", _step_with_function_trace)
    g.add_node("b", _step_with_function_trace)
    g.add_edge(g.START, "a")
    g.add_edge("a", "b")
    g.add_edge("b", g.END)
    runner = g.compile()

    for _ in range(200):  # warm up caches before measuring
        runner.run({"n": 0, "data": {}})

    gc.collect()
    tracemalloc.start()
    try:
        baseline = tracemalloc.take_snapshot()
        for _ in range(2000):
            runner.run({"n": 0, "data": {}})
        gc.collect()
        growth = sum(s.size_diff for s in tracemalloc.take_snapshot().compare_to(baseline, "filename"))
    finally:
        tracemalloc.stop()

    growth_kb = growth / 1024
    limit = 64
    _report("memory growth over 2000 runs (KB)", growth_kb, limit)
    assert growth_kb < limit


# --- Async and parallel paths -------------------------------------------------

@pytest.mark.parametrize("traced", [False, True])
def test_arun_overhead_vs_run(traced):
    """arun() on a sync-only graph should cost about the same as run()."""
    runner = _chain_graph(traced).compile()
    loop = asyncio.new_event_loop()
    try:
        def many_aruns():
            async def go():
                for _ in range(100):
                    await runner.arun({"n": 0, "data": {}})
            loop.run_until_complete(go())

        arun_time = _best_time(many_aruns) / 100
    finally:
        loop.close()
    run_time = _best_time(lambda: runner.run({"n": 0, "data": {}}), number=100)

    ratio = arun_time / run_time
    limit = 3
    _report(f"traced={traced} arun/run ratio", ratio, limit)
    assert ratio < limit


def _parallel_graph(traced: bool, branches: int = 5) -> OrkesGraph:
    """START -> fork -> [b0..b4] -> join -> END."""
    def join(s: S, branch_results):
        s["n"] = sum(r["n"] for r in branch_results.values())
        return s

    g = OrkesGraph(S, traced=traced)
    g.add_node("fork", _step)
    names = [f"b{i}" for i in range(branches)]
    for name in names:
        g.add_node(name, _step)
    g.add_node("join", join)
    g.add_edge(g.START, "fork")
    g.add_parallel_edges("fork", names, "join")
    for name in names:
        g.add_edge(name, "join")
    g.add_edge("join", g.END)
    return g


@pytest.mark.parametrize("traced", [False, True])
def test_parallel_edge_cost_is_node_work_plus_branch_copies(traced):
    """A 5-branch parallel graph runs 7 nodes and, to isolate branches,
    deep-copies the state once at the fork plus once per branch (6 copies).
    Its run should cost about that, not more."""
    branches = 5
    parallel = _parallel_graph(traced, branches).compile()
    chain = _chain_graph(traced).compile()
    state = {"n": 0, "data": {f"k{i}": i for i in range(100)}}

    parallel_time = _best_time(lambda: parallel.run(state), number=100)
    per_node = _best_time(lambda: chain.run(state), number=100) / NUM_NODES
    per_copy = _best_time(lambda: copy.deepcopy(state), number=100)
    expected = per_node * (branches + 2) + per_copy * (branches + 1)

    ratio = parallel_time / expected
    limit = 1.8
    _report(f"traced={traced} parallel / (node work + branch copies) ratio", ratio, limit)
    assert ratio < limit


# --- Cost of tracing ----------------------------------------------------------

def test_tracing_overhead_vs_untraced():
    """Tracing is on by default, so its extra cost per edge (small state) is
    tracked on its own."""
    traced = _chain_graph(traced=True).compile()
    untraced = _chain_graph(traced=False).compile()
    traced_time = _best_time(lambda: traced.run({"n": 0, "data": {}}), number=200)
    untraced_time = _best_time(lambda: untraced.run({"n": 0, "data": {}}), number=200)

    ratio = traced_time / untraced_time
    limit = 12
    _report("traced/untraced ratio", ratio, limit)
    assert ratio < limit


def test_trace_memory_vs_state_size():
    """A traced run keeps one state snapshot per edge, so its trace should take
    about (edges x one state copy) of memory, not more."""
    passes = 200
    runner = _loop_graph(passes, traced=True).compile()
    state = {"n": 0, "data": _big_data(1000)}

    gc.collect()
    tracemalloc.start()
    try:
        one_copy = copy.deepcopy(state)
        state_bytes = tracemalloc.get_traced_memory()[0]
        del one_copy
        gc.collect()
        tracemalloc.reset_peak()
        before = tracemalloc.get_traced_memory()[0]
        runner.run(state)
        trace_bytes = tracemalloc.get_traced_memory()[0] - before
    finally:
        tracemalloc.stop()

    edges = passes + 1
    ratio = trace_bytes / (state_bytes * edges)
    limit = 1.5
    _report("trace memory / (edges x state size) ratio", ratio, limit)
    assert ratio < limit


# --- Import weight --------------------------------------------------------------

def _import_stats(module: str):
    """(import seconds, modules added) for importing `module` in a fresh interpreter."""
    code = (
        "import sys, time\n"
        "before = len(sys.modules)\n"
        "t = time.perf_counter()\n"
        f"import {module}\n"
        "print(time.perf_counter() - t, len(sys.modules) - before)\n"
    )
    best_time, modules = float("inf"), 0
    for _ in range(5):
        out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
        seconds, count = out.stdout.split()
        best_time, modules = min(best_time, float(seconds)), int(count)
    return best_time, modules


# The standard-library modules orkes's graph code itself imports.
STDLIB_REFERENCE = "json, copy, dataclasses, inspect, typing, uuid, contextvars, time, os, itertools, html, re, pathlib"


def test_import_weight_vs_stdlib():
    """The graph API needs only the standard library, so importing it should
    cost about as much as importing the stdlib modules it uses."""
    orkes_time, orkes_modules = _import_stats("orkes.graph")
    stdlib_time, stdlib_modules = _import_stats(STDLIB_REFERENCE)

    time_ratio = orkes_time / stdlib_time
    module_ratio = orkes_modules / stdlib_modules
    _report("import time ratio (orkes.graph / stdlib it uses)", time_ratio, 2)
    _report("modules loaded ratio (orkes.graph / stdlib it uses)", module_ratio, 2)
    assert time_ratio < 2
    assert module_ratio < 2


def test_graph_import_loads_no_third_party_packages():
    """Using graphs must not pull in pydantic or the LLM HTTP libraries."""
    code = (
        "import sys\n"
        "import orkes.graph\n"
        "print(' '.join(sorted({m.split('.')[0] for m in sys.modules})))\n"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    loaded = set(out.stdout.split())
    assert not loaded & {"pydantic", "pydantic_core", "aiohttp", "requests"}


# --- Comparison with LangGraph ---------------------------------------------------

@pytest.mark.parametrize("traced", [False, True])
def test_at_least_5x_faster_than_langgraph(traced):
    """Same 10-node chain in orkes and LangGraph. The README claims orkes is
    5x+ faster; this keeps that true, with and without tracing."""
    langgraph = pytest.importorskip("langgraph.graph")

    class L(TypedDict):
        n: int
        data: dict

    def lg_step(s: L):
        return {"n": s["n"] + 1}

    builder = langgraph.StateGraph(L)
    names = [f"node_{i}" for i in range(NUM_NODES)]
    for name in names:
        builder.add_node(name, lg_step)
    builder.add_edge(langgraph.START, names[0])
    for a, b in zip(names, names[1:]):
        builder.add_edge(a, b)
    builder.add_edge(names[-1], langgraph.END)
    lg = builder.compile()
    orkes_runner = _chain_graph(traced).compile()

    lg_time = _best_time(lambda: lg.invoke({"n": 0, "data": {}}), number=50)
    orkes_time = _best_time(lambda: orkes_runner.run({"n": 0, "data": {}}), number=50)

    ratio = orkes_time / lg_time
    limit = 0.2
    _report(f"traced={traced} orkes/langgraph time ratio", ratio, limit)
    assert ratio < limit
