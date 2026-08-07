import asyncio
import inspect
import time
from typing import Dict, List, TypedDict

import pytest

from orkes.graph.core import OrkesGraph
from orkes.graph.utils import orkes_tracable


class AsyncState(TypedDict):
    log: List[str]
    count: int


def sync_node(state: AsyncState) -> AsyncState:
    state["log"].append("sync_node")
    state["count"] += 1
    return state


async def async_node(state: AsyncState) -> AsyncState:
    await asyncio.sleep(0)
    state["log"].append("async_node")
    state["count"] += 1
    return state


# ---------------------------------------------------------------------------
# Correctness: async nodes execute and produce correct results via arun()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_async_node_end_to_end_via_arun():
    graph = OrkesGraph(state=AsyncState)
    graph.add_node("a", async_node)
    graph.add_edge(graph.START, "a")
    graph.add_edge("a", graph.END)
    app = graph.compile()

    assert app.has_async_components is True

    result = await app.arun({"log": [], "count": 0})

    assert result["log"] == ["async_node"]
    assert result["count"] == 1


@pytest.mark.asyncio
async def test_mixed_sync_and_async_nodes_via_arun():
    graph = OrkesGraph(state=AsyncState)
    graph.add_node("s", sync_node)
    graph.add_node("a", async_node)
    graph.add_edge(graph.START, "s")
    graph.add_edge("s", "a")
    graph.add_edge("a", graph.END)
    app = graph.compile()

    result = await app.arun({"log": [], "count": 0})

    assert result["log"] == ["sync_node", "async_node"]
    assert result["count"] == 2


@pytest.mark.asyncio
async def test_purely_sync_graph_also_works_via_arun():
    """arun() must not be async-node-only -- a graph with no async
    components at all should run correctly through it too."""
    graph = OrkesGraph(state=AsyncState)
    graph.add_node("s", sync_node)
    graph.add_edge(graph.START, "s")
    graph.add_edge("s", graph.END)
    app = graph.compile()

    assert app.has_async_components is False

    result = await app.arun({"log": [], "count": 0})

    assert result["log"] == ["sync_node"]


# ---------------------------------------------------------------------------
# run() must fail fast, before any node executes, on an async-containing graph
# ---------------------------------------------------------------------------

def test_run_raises_on_async_node_before_any_execution():
    side_effects: List[str] = []

    def recording_sync_node(state: AsyncState) -> AsyncState:
        side_effects.append("ran")
        return state

    graph = OrkesGraph(state=AsyncState)
    graph.add_node("s", recording_sync_node)
    graph.add_node("a", async_node)
    graph.add_edge(graph.START, "s")
    graph.add_edge("s", "a")
    graph.add_edge("a", graph.END)
    app = graph.compile()

    with pytest.raises(RuntimeError, match="use arun\\(\\) instead of run\\(\\)"):
        app.run({"log": [], "count": 0})

    # The guard must fire before touching graph_state at all -- "s" (which
    # would run first, well before the async node "a") must never execute.
    assert side_effects == []


# ---------------------------------------------------------------------------
# Async conditional gate functions
# ---------------------------------------------------------------------------

async def async_gate(state: AsyncState) -> str:
    await asyncio.sleep(0)
    return "loop" if state["count"] < 2 else "end"


@pytest.mark.asyncio
async def test_async_conditional_gate_via_arun():
    graph = OrkesGraph(state=AsyncState)
    graph.add_node("s", sync_node)
    graph.add_edge(graph.START, "s")
    graph.add_conditional_edge("s", async_gate, {"loop": "s", "end": "END"}, max_passes=10)
    app = graph.compile()

    assert app.has_async_components is True

    result = await app.arun({"log": [], "count": 0})

    assert result["count"] == 2
    assert result["log"] == ["sync_node", "sync_node"]


async def async_bad_gate(state: AsyncState) -> str:
    await asyncio.sleep(0)
    return "yes"  # not a valid key in the condition map


@pytest.mark.asyncio
async def test_async_gate_invalid_return_raises_informative_keyerror():
    """Mirrors test_conditional_edge_errors.py's sync scenario -- an async
    gate function returning a value absent from its condition map must
    raise the same kind of informative KeyError, not a bare KeyError or a
    swallowed coroutine issue."""
    graph = OrkesGraph(state=AsyncState)
    graph.add_node("s", sync_node)
    graph.add_edge(graph.START, "s")
    graph.add_conditional_edge("s", async_bad_gate, {"true": "END", "false": "END"})
    app = graph.compile()

    with pytest.raises(KeyError, match="Gate function on node 's' returned 'yes'.*\\['true', 'false'\\]"):
        await app.arun({"log": [], "count": 0})


# ---------------------------------------------------------------------------
# orkes_tracable regression: coroutine-ness and real awaited values survive
# decoration, and the trace records the real result, not a coroutine repr
# ---------------------------------------------------------------------------

@orkes_tracable
async def traced_async_fn(x: int) -> int:
    await asyncio.sleep(0)
    return x + 1


def test_orkes_tracable_preserves_coroutine_function_detection():
    assert inspect.iscoroutinefunction(traced_async_fn) is True


async def node_calling_traced_async_helper(state: AsyncState) -> AsyncState:
    result = await traced_async_fn(state["count"])
    state["count"] = result
    return state


@pytest.mark.asyncio
async def test_orkes_tracable_async_records_real_awaited_value_in_trace():
    graph = OrkesGraph(state=AsyncState)
    graph.add_node("a", node_calling_traced_async_helper)
    graph.add_edge(graph.START, "a")
    graph.add_edge("a", graph.END)
    app = graph.compile()

    result = await app.arun({"log": [], "count": 5})
    assert result["count"] == 6

    edge_with_fn_trace = next(
        (e for e in app.trace.edges_trace if e.function_traces), None
    )
    assert edge_with_fn_trace is not None
    function_trace = edge_with_fn_trace.function_traces[0]

    # Must be the real awaited integer, not a coroutine repr like
    # "<coroutine object ... at 0x...>".
    assert function_trace.return_value == 6
    assert function_trace.function_name == "traced_async_fn"


# ---------------------------------------------------------------------------
# Parallel-branch isolation, ported to arun() with async branch functions --
# the highest-risk regression surface, since _arun_parallel_branches mirrors
# (rather than reuses) the swap/deepcopy/restore logic that fixed the
# cross-branch leak bug in commit 2d011b5.
# ---------------------------------------------------------------------------

class ParallelIsolationState(TypedDict):
    shared_counter: int
    a_saw: int
    b_saw: int


def iso_start(state: ParallelIsolationState) -> ParallelIsolationState:
    return state


async def iso_branch_a(state: ParallelIsolationState) -> ParallelIsolationState:
    await asyncio.sleep(0)
    state["a_saw"] = state["shared_counter"]
    state["shared_counter"] += 1
    return state


async def iso_branch_b(state: ParallelIsolationState) -> ParallelIsolationState:
    await asyncio.sleep(0)
    state["b_saw"] = state["shared_counter"]
    state["shared_counter"] += 1
    return state


def iso_agg(
    state: ParallelIsolationState, branch_results: Dict[str, ParallelIsolationState]
) -> ParallelIsolationState:
    state["a_saw"] = branch_results["branch_a"]["a_saw"]
    state["b_saw"] = branch_results["branch_b"]["b_saw"]
    return state


@pytest.mark.asyncio
async def test_async_parallel_branches_do_not_observe_each_others_writes():
    graph = OrkesGraph(state=ParallelIsolationState)
    graph.add_node("start", iso_start)
    graph.add_node("branch_a", iso_branch_a)
    graph.add_node("branch_b", iso_branch_b)
    graph.add_node("agg", iso_agg)

    graph.add_edge(graph.START, "start")
    graph.add_parallel_edges("start", ["branch_a", "branch_b"], "agg")
    graph.add_edge("branch_a", "agg")
    graph.add_edge("branch_b", "agg")
    graph.add_edge("agg", graph.END)

    app = graph.compile()
    final_state = await app.arun({"shared_counter": 0, "a_saw": -1, "b_saw": -1})

    # Both branches must start from the same pre-fork snapshot (counter == 0)
    # regardless of which one physically ran first -- same guarantee as the
    # existing sync test, now under arun()'s independently-written branch loop.
    assert final_state["a_saw"] == 0
    assert final_state["b_saw"] == 0


class ParallelMutableIsolationState(TypedDict):
    shared_log: List[str]
    a_saw_len: int
    b_saw_len: int


def mut_start(state: ParallelMutableIsolationState) -> ParallelMutableIsolationState:
    return state


async def mut_branch_a(state: ParallelMutableIsolationState) -> ParallelMutableIsolationState:
    await asyncio.sleep(0)
    state["a_saw_len"] = len(state["shared_log"])
    state["shared_log"].append("A")
    return state


async def mut_branch_b(state: ParallelMutableIsolationState) -> ParallelMutableIsolationState:
    await asyncio.sleep(0)
    state["b_saw_len"] = len(state["shared_log"])
    state["shared_log"].append("B")
    return state


def mut_agg(
    state: ParallelMutableIsolationState, branch_results: Dict[str, ParallelMutableIsolationState]
) -> ParallelMutableIsolationState:
    state["a_saw_len"] = branch_results["branch_a"]["a_saw_len"]
    state["b_saw_len"] = branch_results["branch_b"]["b_saw_len"]
    state["shared_log"] = branch_results["branch_a"]["shared_log"]
    return state


@pytest.mark.asyncio
async def test_async_parallel_branches_deep_copy_mutable_state():
    """Regression test for the exact shallow-copy aliasing bug commit
    2d011b5 fixed, now exercised through the async branch-execution path."""
    graph = OrkesGraph(state=ParallelMutableIsolationState)
    graph.add_node("start", mut_start)
    graph.add_node("branch_a", mut_branch_a)
    graph.add_node("branch_b", mut_branch_b)
    graph.add_node("agg", mut_agg)

    graph.add_edge(graph.START, "start")
    graph.add_parallel_edges("start", ["branch_a", "branch_b"], "agg")
    graph.add_edge("branch_a", "agg")
    graph.add_edge("branch_b", "agg")
    graph.add_edge("agg", graph.END)

    app = graph.compile()
    final_state = await app.arun({"shared_log": [], "a_saw_len": -1, "b_saw_len": -1})

    assert final_state["a_saw_len"] == 0
    assert final_state["b_saw_len"] == 0
    assert len(final_state["shared_log"]) == 1


# ---------------------------------------------------------------------------
# Re-entrancy guard: concurrent calls on ONE instance must fail explicitly;
# the documented pattern (one compile()'d instance per concurrent run) works.
# ---------------------------------------------------------------------------

async def slow_async_node(state: AsyncState) -> AsyncState:
    await asyncio.sleep(0.05)
    state["log"].append("slow_async_node")
    return state


def _build_slow_graph() -> OrkesGraph:
    graph = OrkesGraph(state=AsyncState)
    graph.add_node("a", slow_async_node)
    graph.add_edge(graph.START, "a")
    graph.add_edge("a", graph.END)
    return graph


@pytest.mark.asyncio
async def test_concurrent_arun_on_same_instance_raises_reentrancy_error():
    app = _build_slow_graph().compile()

    results = await asyncio.gather(
        app.arun({"log": [], "count": 0}),
        app.arun({"log": [], "count": 0}),
        return_exceptions=True,
    )

    errors = [r for r in results if isinstance(r, RuntimeError)]
    successes = [r for r in results if not isinstance(r, Exception)]

    assert len(errors) == 1
    assert "already executing a run" in str(errors[0])
    assert len(successes) == 1


@pytest.mark.asyncio
async def test_concurrent_arun_on_separate_compiled_instances_succeeds():
    """The documented, correct pattern -- mirrors
    test_llm_trace_race_condition.py's existing sync precedent (N separate
    compile()'d instances), now exercised for arun()."""
    apps = [_build_slow_graph().compile() for _ in range(3)]

    results = await asyncio.gather(
        *(app.arun({"log": [], "count": 0}) for app in apps)
    )

    for result in results:
        assert result["log"] == ["slow_async_node"]


def test_run_reentrancy_guard_exists_and_defaults_false():
    """The _running guard is instance-scoped and must default to False --
    a fresh compile() must never start out already "running"."""
    app = _build_slow_graph().compile()
    assert app._running is False


# ---------------------------------------------------------------------------
# Concurrency trial: arun() must provide a real concurrency benefit over
# sequential run() for I/O-bound (await-based) work -- not just "doesn't
# crash." N concurrent arun() calls (separate instances, per the guard
# above) should take roughly one DELAY, not N * DELAY; N sequential run()
# calls on an equivalent blocking (time.sleep) graph should take roughly
# N * DELAY.
# ---------------------------------------------------------------------------

DELAY = 0.1
N = 5


class TimingState(TypedDict):
    ticks: int


async def async_delay_node(state: TimingState) -> TimingState:
    await asyncio.sleep(DELAY)
    state["ticks"] += 1
    return state


def sync_delay_node(state: TimingState) -> TimingState:
    time.sleep(DELAY)
    state["ticks"] += 1
    return state


def _build_async_delay_app() -> OrkesGraph:
    graph = OrkesGraph(state=TimingState)
    graph.add_node("d", async_delay_node)
    graph.add_edge(graph.START, "d")
    graph.add_edge("d", graph.END)
    return graph.compile()


def _build_sync_delay_app() -> OrkesGraph:
    graph = OrkesGraph(state=TimingState)
    graph.add_node("d", sync_delay_node)
    graph.add_edge(graph.START, "d")
    graph.add_edge("d", graph.END)
    return graph.compile()


def test_sequential_run_takes_roughly_n_times_delay():
    apps = [_build_sync_delay_app() for _ in range(N)]

    start = time.perf_counter()
    for app in apps:
        app.run({"ticks": 0})
    elapsed = time.perf_counter() - start

    # Sequential, blocking work: no way around paying the full N * DELAY.
    # Generous lower bound to avoid flakiness while still proving it's not
    # accidentally running concurrently.
    assert elapsed >= DELAY * (N - 1)


@pytest.mark.asyncio
async def test_concurrent_arun_takes_roughly_one_delay_not_n_times_delay():
    apps = [_build_async_delay_app() for _ in range(N)]

    start = time.perf_counter()
    results = await asyncio.gather(*(app.arun({"ticks": 0}) for app in apps))
    elapsed = time.perf_counter() - start

    for result in results:
        assert result["ticks"] == 1

    # This is the actual point of arun(): N concurrent awaited calls on N
    # separate instances should overlap during their sleep, so total time
    # should be close to one DELAY, not N. Generous upper bound (well under
    # N * DELAY) to avoid flakiness while still proving real concurrency.
    assert elapsed < DELAY * (N / 2)
