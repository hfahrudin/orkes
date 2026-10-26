"""Regression tests for bugs found in the runner, tracing, connectors and
trace inspector. Each test reproduces one reported bug."""
import json
import os
import datetime
from typing import TypedDict
from unittest import mock

import pytest

from orkes.graph.core import OrkesGraph
from orkes.graph.utils import orkes_tracable, function_assertion


class S(TypedDict):
    n: int
    items: list


def _linear_graph(node_fn, state=S, **graph_kwargs):
    g = OrkesGraph(state, **graph_kwargs)
    g.add_node("node", node_fn)
    g.add_edge(g.START, "node")
    g.add_edge("node", g.END)
    return g


def _loop_graph(node_fn, loops=3):
    """START -> loop (runs `loops` times) -> END."""
    def gate(s: S):
        return "again" if s["n"] < loops else "done"

    g = OrkesGraph(S)
    g.add_node("loop", node_fn)
    g.add_edge(g.START, "loop")
    g.add_conditional_edge("loop", gate, {"again": "loop", "done": "END"})
    return g


def _inc(s: S):
    s["n"] += 1
    return s


# --- Per-run state reset -------------------------------------------------

def test_compiled_graph_survives_more_runs_than_max_passes():
    """Edge pass counts used to persist across runs, so run 26 hit max_passes."""
    runner = _linear_graph(_inc).compile()
    for _ in range(30):
        runner.run({"n": 0, "items": []})


def test_untraced_graph_survives_more_runs_than_max_passes():
    runner = _linear_graph(_inc, traced=False).compile()
    for _ in range(30):
        runner.run({"n": 0, "items": []})


def test_each_run_gets_fresh_run_id_trace_and_counter():
    runner = _linear_graph(_inc).compile()
    runner.run({"n": 0, "items": []})
    first_id, first_trace = runner.run_id, runner.trace

    runner.run({"n": 0, "items": []})

    assert runner.run_id != first_id
    assert runner.trace.run_id == runner.run_id
    assert runner.trace is not first_trace
    assert len(runner.trace.edges_trace) == 2  # START->node, node->END only
    assert [e.edge_run_number for e in runner.trace.edges_trace] == [1, 2]


def test_separate_compiles_do_not_share_pass_counters():
    """Runners compiled from the same graph used to share Edge.passes."""
    g = OrkesGraph(S)
    g.add_node("node", _inc)
    g.add_edge(g.START, "node", max_passes=1)
    g.add_edge("node", g.END, max_passes=1)
    r1, r2 = g.compile(), g.compile()

    r1.run({"n": 0, "items": []})
    r2.run({"n": 0, "items": []})  # used to raise: edge passed 1 times


@pytest.mark.asyncio
async def test_arun_survives_more_runs_than_max_passes_and_resets():
    runner = _linear_graph(_inc).compile()
    ids = set()
    for _ in range(30):
        await runner.arun({"n": 0, "items": []})
        ids.add(runner.run_id)
    assert len(ids) == 30
    assert len(runner.trace.edges_trace) == 2


# --- Trace contents ------------------------------------------------------

def test_state_snapshot_is_not_changed_by_later_nodes():
    """Snapshots were shallow copies, so in-place list changes leaked into them."""
    def append(s: S):
        s["items"].append("x")
        return s

    runner = _linear_graph(append).compile()
    runner.run({"n": 0, "items": []})

    node_edge = runner.trace.edges_trace[1]  # node -> END, snapshot taken before `append` ran
    assert node_edge.state_snapshot["items"] == []


def test_function_traces_are_recorded_once_per_traversal():
    """Edge traces were shallow copies sharing one function_traces list."""
    @orkes_tracable
    def helper(x):
        return x

    def loop(s: S):
        helper(s["n"])
        s["n"] += 1
        return s

    runner = _loop_graph(loop).compile()
    for _ in range(2):  # second run must not see the first run's calls either
        runner.run({"n": 0, "items": []})
        counts = [len(e.function_traces) for e in runner.trace.edges_trace if e.from_node == "loop"]
        assert counts == [1, 1, 1]


def test_llm_call_with_callable_tools_is_traced():
    """LLMTraceSchema rejected callables in `tools`, failing the node after the API call."""
    from orkes.services.connectors import LLMFactory
    from orkes.shared.schema import OrkesMessagesSchema, OrkesMessageSchema

    client = LLMFactory.create_openai(api_key="test")

    def get_weather(city: str) -> str:
        """Get the weather for a city."""
        return "sunny"

    def node(s: S):
        client.send_message(
            OrkesMessagesSchema(messages=[OrkesMessageSchema(role="user", content="hi")]),
            tools=[get_weather],
        )
        return s

    response = mock.Mock()
    response.raise_for_status = lambda: None
    response.json = lambda: {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}

    runner = _linear_graph(node).compile()
    with mock.patch("orkes.services.connectors.requests.post", return_value=response):
        for _ in range(2):
            runner.run({"n": 0, "items": []})
            llm_traces = runner.trace.edges_trace[1].llm_traces
            assert len(llm_traces) == 1
            assert llm_traces[0].tools[0]["name"] == "get_weather"


# --- Failures --------------------------------------------------------------

class Boom(Exception):
    pass


def _failing_node(s: S):
    raise Boom("node exploded")


def _assert_failed_trace(runner):
    trace = runner.trace
    assert trace.status == "FAILED"
    assert trace.elapsed_time > 0
    assert trace.error == "Boom: node exploded"
    failing_edge = trace.edges_trace[-1]
    assert failing_edge.from_node == "node"
    assert failing_edge.error == "Boom: node exploded"


def test_failed_run_records_status_error_elapsed_and_failing_edge():
    runner = _linear_graph(_failing_node).compile()
    with pytest.raises(Boom) as exc_info:
        runner.run({"n": 0, "items": []})
    assert str(exc_info.value) == "node exploded"  # original exception, unchanged
    _assert_failed_trace(runner)


@pytest.mark.asyncio
async def test_failed_arun_records_status_error_elapsed_and_failing_edge():
    runner = _linear_graph(_failing_node).compile()
    with pytest.raises(Boom):
        await runner.arun({"n": 0, "items": []})
    _assert_failed_trace(runner)


def test_failed_run_is_auto_saved(tmp_path):
    runner = _linear_graph(_failing_node).compile()
    runner.traces_dir = str(tmp_path)
    runner.auto_save_trace = True
    with pytest.raises(Boom):
        runner.run({"n": 0, "items": []})
    saved = json.loads((tmp_path / f"trace_{runner.run_id}.json").read_text())
    assert saved["status"] == "FAILED"
    assert saved["error"] == "Boom: node exploded"


def test_successful_run_has_no_error():
    runner = _linear_graph(_inc).compile()
    runner.run({"n": 0, "items": []})
    assert runner.trace.status == "FINISHED"
    assert runner.trace.error is None
    assert all(e.error is None for e in runner.trace.edges_trace)


def test_node_returning_none_gives_clear_error():
    def forgets_return(s: S):
        s["n"] = 1

    runner = _linear_graph(forgets_return).compile()
    with pytest.raises(TypeError, match="Node 'node' must return the state dict"):
        runner.run({"n": 0, "items": []})


# --- Node / gate function signatures ----------------------------------------

def test_lambda_gate_function_is_accepted():
    """The README quickstart uses a lambda gate, which used to be rejected."""
    g = OrkesGraph(S)
    g.add_node("node", _inc)
    g.add_edge(g.START, "node")
    g.add_conditional_edge("node", lambda s: "end", {"end": "END"})
    assert g.compile().run({"n": 0, "items": []})["n"] == 1


def test_postponed_annotations_are_accepted(tmp_path):
    """`from __future__ import annotations` turns annotations into strings."""
    module = tmp_path / "postponed_graph.py"
    module.write_text(
        "from __future__ import annotations\n"
        "from typing import TypedDict\n"
        "class P(TypedDict):\n"
        "    x: int\n"
        "def node(s: P):\n"
        "    s['x'] += 1\n"
        "    return s\n"
    )
    namespace = {}
    exec(compile(module.read_text(), str(module), "exec"), namespace)

    g = OrkesGraph(namespace["P"])
    g.add_node("node", namespace["node"])
    g.add_edge(g.START, "node")
    g.add_edge("node", g.END)
    assert g.compile().run({"x": 0})["x"] == 1


def test_function_with_wrong_annotation_is_still_rejected():
    def wrong(s: int):
        return s

    def no_params():
        return {}

    assert not function_assertion(wrong, S)
    assert not function_assertion(no_params, S)
    with pytest.raises(TypeError):
        OrkesGraph(S).add_node("wrong", wrong)


# --- Input handling ---------------------------------------------------------

def test_run_does_not_modify_callers_dict():
    def set_n(s: S):
        s["n"] = 99
        return s

    runner = _linear_graph(set_n).compile()
    inp = {"n": 0, "items": []}
    out = runner.run(inp)
    assert out is not inp
    assert inp["n"] == 0
    assert out["n"] == 99


# --- Saving and visualizing traces ------------------------------------------

class D(TypedDict):
    when: datetime.datetime


def test_save_and_visualize_with_non_json_state(tmp_path):
    def node(s: D):
        return s

    runner = _linear_graph(node, state=D).compile()
    runner.traces_dir = str(tmp_path)
    runner.run({"when": datetime.datetime(2026, 1, 1)})

    runner.save_run_trace()
    runner.visualize_trace()

    saved = json.loads((tmp_path / f"trace_{runner.run_id}.json").read_text())
    assert "2026-01-01" in saved["edges_trace"][1]["state_snapshot"]["when"]
    assert os.path.exists(tmp_path / f"trace_{runner.run_id}_inspector.html")


def test_inspector_escapes_trace_data():
    """State text containing </script> used to break out of the page's script block."""
    from orkes.visualizer.generator import TraceInspector

    class T(TypedDict):
        text: str

    def node(s: T):
        return s

    payload = "</script><script>alert(1)</script>"
    runner = _linear_graph(node, state=T, name="<b>graph</b>").compile()
    runner.run({"text": payload})

    page = TraceInspector().generate_html(runner.trace.model_dump())

    assert payload not in page
    assert "\\u003c/script\\u003e" in page
    assert "<b>graph</b>" not in page
    assert "&lt;b&gt;graph&lt;/b&gt;" in page


def test_inspector_placeholder_text_in_data_is_not_substituted():
    from orkes.visualizer.generator import TraceInspector

    class T(TypedDict):
        text: str

    def node(s: T):
        return s

    runner = _linear_graph(node, state=T).compile()
    runner.run({"text": "JSON_EDGES TITLE_CARD_CONTENT"})

    page = TraceInspector().generate_html(runner.trace.model_dump())
    assert "JSON_EDGES TITLE_CARD_CONTENT" in page
