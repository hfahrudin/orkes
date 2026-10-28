"""End-to-end check against a running Orkes Watcher (integration agreement §5).

Sends one run per scenario through WatcherSink, then prints what each run
should look like in the dashboard. Not collected by pytest; run it directly:

    ORKES_WATCHER_KEY=<project ingest key> python tests/e2e/watcher_e2e.py

ORKES_WATCHER_URL defaults to http://localhost:8000 (the watcher backend).
"""
import os
import subprocess
import sys
import textwrap
import time
from typing import TypedDict

from orkes.exporters.watcher import WatcherSink
from orkes.graph.core import OrkesGraph

URL = os.environ.get("ORKES_WATCHER_URL", "http://localhost:8000")
KEY = os.environ.get("ORKES_WATCHER_KEY")


class S(TypedDict):
    n: int
    data: dict


def step(s: S):
    s["n"] += 1
    return s


def boom(s: S):
    raise ValueError("boom")


def join(s: S, branch_results):
    s["n"] = sum(r["n"] for r in branch_results.values())
    return s


def graph(name, sink, build):
    g = OrkesGraph(S, name=name, description=f"e2e: {name}", trace_sinks=[sink])
    build(g)
    return g.compile()


def linear(g):
    g.add_node("a", step)
    g.add_node("b", step)
    g.add_edge(g.START, "a")
    g.add_edge("a", "b")
    g.add_edge("b", g.END)


def loop(g):
    g.add_node("loop", step)
    g.add_edge(g.START, "loop")
    g.add_conditional_edge("loop", lambda s: "again" if s["n"] < 5 else "done", {"again": "loop", "done": "END"})


def parallel(g):
    for name in ("split", "b1", "b2"):
        g.add_node(name, step)
    g.add_node("join", join)
    g.add_edge(g.START, "split")
    g.add_parallel_edges("split", ["b1", "b2"], "join")
    g.add_edge("b1", "join")
    g.add_edge("b2", "join")
    g.add_edge("join", g.END)


def fails_in_node(g):
    g.add_node("a", step)
    g.add_node("bad", boom)
    g.add_edge(g.START, "a")
    g.add_edge("a", "bad")
    g.add_edge("bad", g.END)


def fails_in_gate(g):
    g.add_node("a", step)
    g.add_node("b", step)
    g.add_edge(g.START, "a")
    g.add_conditional_edge("a", boom, {"x": "b"})
    g.add_edge("b", g.END)


def run(label, runner, state=None, *, expect):
    try:
        runner.run(state or {"n": 0, "data": {}})
    except ValueError:
        pass
    print(f"  {label:<28} run {runner.run_id}  -> expect {expect}")


SCRIPT = """
import time
from typing import TypedDict
from orkes.graph.core import OrkesGraph
from orkes.exporters.watcher import WatcherSink

class S(TypedDict):
    n: int

def a(s: S):
    s["n"] += 1
    return s

def slow(s: S):
    time.sleep({sleep})
    return s

g = OrkesGraph(S, name="{name}", trace_sinks=[WatcherSink("{key}", "{url}")])
g.add_node("a", a)
g.add_node("slow", slow)
g.add_edge(g.START, "a")
g.add_edge("a", "slow")
g.add_edge("slow", g.END)
g.compile().run({{"n": 0}})
"""


def main():
    if not KEY:
        sys.exit("Set ORKES_WATCHER_KEY to a project ingest key (see the watcher's Keys page).")
    sink = WatcherSink(KEY, URL)
    print(f"Sending to {URL}\n")

    run("linear", graph("e2e-linear", sink, linear), expect="finished, 3 edges, 0 loops")
    run("loop", graph("e2e-loop", sink, loop), expect="finished, loop count 4")
    run("parallel", graph("e2e-parallel", sink, parallel), expect="finished, list to_node split -> b1, b2")
    run("raises in node", graph("e2e-fail-node", sink, fails_in_node), expect="failed, failed_node 'bad', ValueError traceback")
    run("raises in gate", graph("e2e-fail-gate", sink, fails_in_gate), expect="failed, failed_node 'a', last edge to 'N/A'")
    big = {"n": 0, "data": {"blob": "x" * 300_000}}
    run("state over 256 KB", graph("e2e-big-state", sink, linear), big, expect="finished, state_snapshot shows truncated")

    runner = graph("e2e-30-runs", sink, linear)
    for _ in range(30):
        runner.run({"n": 0, "data": {}})
    print(f"  {'30 runs, one graph':<28} graph 'e2e-30-runs'  -> expect 30 finished runs")

    script = SCRIPT.format(sleep=0, name="e2e-short-script", key=KEY, url=URL)
    subprocess.run([sys.executable, "-c", script], check=True)
    print(f"  {'script exits after run()':<28} graph 'e2e-short-script'  -> expect finished, not running")

    script = SCRIPT.format(sleep=3600, name="e2e-killed", key=KEY, url=URL)
    proc = subprocess.Popen([sys.executable, "-c", script])
    time.sleep(2)
    proc.kill()
    print(f"  {'process killed mid-run':<28} graph 'e2e-killed'  -> expect running, then failed 'abandoned' after the project's timeout")

    start = time.time()
    closed = WatcherSink(KEY, "http://127.0.0.1:9")
    graph("e2e-closed-port", closed, linear).run({"n": 0, "data": {}})
    print(f"  {'closed port':<28} not sent; run took {time.time() - start:.1f}s (expect <= 3s extra)")


if __name__ == "__main__":
    main()
