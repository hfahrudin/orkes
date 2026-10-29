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
from orkes.shared.schema import to_dict


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
    assert trace.error.startswith("Boom: node exploded\nTraceback (most recent call last):")
    assert trace.failed_node == "node"
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
    assert saved["error"].startswith("Boom: node exploded\n")
    assert saved["failed_node"] == "node"


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

    page = TraceInspector().generate_html(to_dict(runner.trace))

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

    page = TraceInspector().generate_html(to_dict(runner.trace))
    assert "JSON_EDGES TITLE_CARD_CONTENT" in page


# --- LLM provider payloads ----------------------------------------------------

def _tool_round_trip_messages():
    """A user question, the assistant's tool calls, and both tool results."""
    from orkes.shared.schema import OrkesMessagesSchema, OrkesMessageSchema

    calls = [
        {"function_name": "get_weather", "arguments": {"city": "SF"}, "id": "call_1"},
        {"function_name": "get_time", "arguments": {}, "id": "call_2"},
    ]
    return OrkesMessagesSchema(messages=[
        OrkesMessageSchema(role="system", content="be brief"),
        OrkesMessageSchema(role="user", content="weather and time?"),
        OrkesMessageSchema(role="assistant", content=calls, content_type="tool_calls"),
        OrkesMessageSchema(role="tool", content="sunny", tool_call_id="call_1"),
        OrkesMessageSchema(role="tool", content="noon", tool_call_id="call_2"),
    ])


def test_messages_payload_has_no_null_extra_fields():
    """Every message used to carry content_type/tool_call_id = null, which
    Anthropic's API rejects as unknown fields."""
    from orkes.shared.schema import OrkesMessagesSchema
    from orkes.services.strategies import OpenAIStyleStrategy, AnthropicStrategy

    messages = OrkesMessagesSchema(messages=[{"role": "user", "content": "hi"}])
    assert OpenAIStyleStrategy().get_messages_payload(messages)["messages"] == [{"role": "user", "content": "hi"}]
    assert AnthropicStrategy().get_messages_payload(messages)["messages"] == [{"role": "user", "content": "hi"}]


@pytest.mark.parametrize("strategy_name, response, expected_id", [
    ("OpenAIStyleStrategy",
     {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
         {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": "{\"city\": \"SF\"}"}}]}}]},
     "call_1"),
    ("AnthropicStrategy",
     {"content": [{"type": "tool_use", "id": "toolu_1", "name": "get_weather", "input": {"city": "SF"}}]},
     "toolu_1"),
    ("GoogleGeminiStrategy",
     {"candidates": [{"content": {"parts": [{"functionCall": {"id": "fc_1", "name": "get_weather", "args": {"city": "SF"}}}]}}]},
     "fc_1"),
])
def test_tool_call_id_is_kept(strategy_name, response, expected_id):
    """The provider's tool call id used to be dropped, so tool results couldn't be sent back."""
    from orkes.services import strategies

    parsed = getattr(strategies, strategy_name)().parse_response(response)
    assert parsed.content_type == "tool_calls"
    assert parsed.content[0].id == expected_id
    assert parsed.content[0].arguments == {"city": "SF"}


def test_openai_tool_round_trip_payload():
    from orkes.services.strategies import OpenAIStyleStrategy

    messages = OpenAIStyleStrategy().get_messages_payload(_tool_round_trip_messages())["messages"]
    assert messages[0] == {"role": "system", "content": "be brief"}
    assert messages[2] == {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_1", "type": "function", "function": {"name": "get_weather", "arguments": "{\"city\": \"SF\"}"}},
        {"id": "call_2", "type": "function", "function": {"name": "get_time", "arguments": "{}"}},
    ]}
    assert messages[3] == {"role": "tool", "content": "sunny", "tool_call_id": "call_1"}
    assert messages[4] == {"role": "tool", "content": "noon", "tool_call_id": "call_2"}


def test_anthropic_tool_round_trip_payload():
    from orkes.services.strategies import AnthropicStrategy

    payload = AnthropicStrategy().get_messages_payload(_tool_round_trip_messages())
    assert payload["system"] == "be brief"
    assert payload["messages"] == [
        {"role": "user", "content": "weather and time?"},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "call_1", "name": "get_weather", "input": {"city": "SF"}},
            {"type": "tool_use", "id": "call_2", "name": "get_time", "input": {}},
        ]},
        # both results of the parallel calls go in one user message
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "call_1", "content": "sunny"},
            {"type": "tool_result", "tool_use_id": "call_2", "content": "noon"},
        ]},
    ]


def test_parsed_tool_calls_can_be_sent_back():
    """The documented loop: parse a reply, append it plus the results, send again."""
    from orkes.shared.schema import OrkesMessagesSchema, OrkesMessageSchema, to_dict
    from orkes.services.strategies import OpenAIStyleStrategy

    strategy = OpenAIStyleStrategy()
    reply = to_dict(strategy.parse_response({"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
        {"id": "call_9", "type": "function", "function": {"name": "get_weather", "arguments": "{\"city\": \"SF\"}"}}]}}]}))

    messages = OrkesMessagesSchema(messages=[{"role": "user", "content": "weather?"}])
    messages.messages.append(OrkesMessageSchema(role="assistant", content=reply["content"], content_type="tool_calls"))
    messages.messages.append(OrkesMessageSchema(role="tool", content="sunny", tool_call_id=reply["content"][0]["id"]))

    sent = strategy.get_messages_payload(messages)["messages"]
    assert sent[1]["tool_calls"][0]["id"] == sent[2]["tool_call_id"] == "call_9"


# --- Aggregation node reached without its fork --------------------------------

def test_aggregation_node_reentered_gets_empty_branch_results():
    """A loop back into an aggregation node used to pass branch_results=None."""
    seen = []

    def fork(s: S):
        return s

    def branch(s: S):
        s["n"] += 1
        return s

    def join(s: S, branch_results):
        seen.append(sorted(branch_results))
        s["items"] = s["items"] + [len(branch_results)]
        return s

    def gate(s: S):
        return "again" if len(s["items"]) < 2 else "done"

    g = OrkesGraph(S)
    g.add_node("fork", fork)
    g.add_node("a", branch)
    g.add_node("b", branch)
    g.add_node("join", join)
    g.add_edge(g.START, "fork")
    g.add_parallel_edges("fork", ["a", "b"], "join")
    g.add_edge("a", "join")
    g.add_edge("b", "join")
    g.add_conditional_edge("join", gate, {"again": "join", "done": "END"})

    result = g.compile().run({"n": 0, "items": []})
    assert seen == [["a", "b"], []]  # via the fork, then the loop back
    assert result["items"] == [2, 0]


# --- Gemini, Anthropic system prompts, LLM defaults ---------------------------

def test_gemini_system_prompt_is_a_system_instruction():
    """System messages used to be sent as 'model' turns, as if the model had said them."""
    from orkes.shared.schema import OrkesMessagesSchema
    from orkes.services.strategies import GoogleGeminiStrategy

    messages = OrkesMessagesSchema(messages=[
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ])
    payload = GoogleGeminiStrategy().get_messages_payload(messages)
    assert payload["system_instruction"] == {"parts": [{"text": "be brief"}]}
    assert payload["contents"] == [
        {"role": "user", "parts": [{"text": "hi"}]},
        {"role": "model", "parts": [{"text": "hello"}]},
    ]


def test_gemini_tool_round_trip_payload():
    from orkes.services.strategies import GoogleGeminiStrategy

    payload = GoogleGeminiStrategy().get_messages_payload(_tool_round_trip_messages())
    assert payload["system_instruction"] == {"parts": [{"text": "be brief"}]}
    assert payload["contents"] == [
        {"role": "user", "parts": [{"text": "weather and time?"}]},
        {"role": "model", "parts": [
            {"functionCall": {"name": "get_weather", "args": {"city": "SF"}, "id": "call_1"}},
            {"functionCall": {"name": "get_time", "args": {}, "id": "call_2"}},
        ]},
        # results matched to their function by call id, grouped in one turn
        {"role": "user", "parts": [
            {"functionResponse": {"name": "get_weather", "response": {"result": "sunny"}, "id": "call_1"}},
            {"functionResponse": {"name": "get_time", "response": {"result": "noon"}, "id": "call_2"}},
        ]},
    ]


def test_all_system_messages_are_kept():
    """Anthropic used to keep only the first system message."""
    from orkes.shared.schema import OrkesMessagesSchema
    from orkes.services.strategies import AnthropicStrategy, GoogleGeminiStrategy

    messages = OrkesMessagesSchema(messages=[
        {"role": "system", "content": "be brief"},
        {"role": "system", "content": "answer in French"},
        {"role": "user", "content": "hi"},
    ])
    assert AnthropicStrategy().get_messages_payload(messages)["system"] == "be brief\n\nanswer in French"
    gemini = GoogleGeminiStrategy().get_messages_payload(messages)
    assert gemini["system_instruction"]["parts"][0]["text"] == "be brief\n\nanswer in French"


def test_factory_defaults_avoid_rejected_settings():
    """Newer OpenAI models reject `max_tokens`; current Claude models reject
    non-default `temperature`; the old Claude default model is retired."""
    from orkes.services.connectors import LLMFactory

    openai = LLMFactory.create_openai(api_key="k")
    assert openai.config.default_params == {"max_completion_tokens": 1024}

    anthropic = LLMFactory.create_anthropic(api_key="k")
    assert anthropic.config.model == "claude-opus-5-5"
    assert anthropic.config.default_params == {"max_tokens": 16000}


def test_empty_default_params_means_none():
    from orkes.services.connectors import LLMConfig

    assert LLMConfig(api_key="k", base_url="u", model="m", default_params={}).default_params == {}


def test_requests_use_a_timeout():
    """Requests had no timeout, so a stuck provider could hang a graph forever."""
    from orkes.services.connectors import LLMFactory
    from orkes.shared.schema import OrkesMessagesSchema

    client = LLMFactory.create_openai(api_key="k")
    response = mock.Mock()
    response.raise_for_status = lambda: None
    response.json = lambda: {"choices": [{"message": {"role": "assistant", "content": "ok"}}]}
    with mock.patch("orkes.services.connectors.requests.post", return_value=response) as post, \
            mock.patch("orkes.services.connectors.requests.get", return_value=mock.Mock(status_code=200)) as get:
        client.send_message(OrkesMessagesSchema(messages=[{"role": "user", "content": "hi"}]))
        assert client.health_check()
    assert post.call_args.kwargs["timeout"] == 600.0
    assert get.call_args.kwargs["timeout"] == 600.0
    assert get.call_args.args[0].endswith("/models")


@pytest.mark.asyncio
async def test_streamed_llm_call_is_traced():
    """Streaming calls were never recorded in the trace."""
    from orkes.services.connectors import LLMFactory
    from orkes.shared.schema import OrkesMessagesSchema

    client = LLMFactory.create_openai(api_key="k")
    lines = [
        b'data: {"choices": [{"delta": {"content": "Hel"}}]}\n',
        b'data: {"choices": [{"delta": {"content": "lo"}}]}\n',
        b'data: [DONE]\n',
    ]

    class FakeResponse:
        def raise_for_status(self):
            pass

        @property
        def content(self):
            async def gen():
                for line in lines:
                    yield line
            return gen()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    class FakeSession:
        def __init__(self, *args, **kwargs):
            pass

        def post(self, *args, **kwargs):
            return FakeResponse()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *exc):
            return False

    async def node(s: S):
        text = ""
        async for chunk in client.stream_message(OrkesMessagesSchema(messages=[{"role": "user", "content": "hi"}])):
            text += chunk
        s["items"] = [text]
        return s

    runner = _linear_graph(node).compile()
    with mock.patch("orkes.services.connectors.aiohttp.ClientSession", FakeSession):
        result = await runner.arun({"n": 0, "items": []})

    assert result["items"] == ["Hello"]
    [llm_trace] = runner.trace.edges_trace[1].llm_traces
    assert llm_trace.parsed_response.content == "Hello"


def test_loop_limit_error_names_the_nodes():
    """The error used to show only a random edge id."""
    g = OrkesGraph(S)
    g.add_node("loop", _inc)
    g.add_edge(g.START, "loop")
    g.add_conditional_edge("loop", lambda s: "again", {"again": "loop", "done": "END"}, max_passes=3)
    with pytest.raises(RuntimeError, match=r"conditional edge from 'loop' .* limit of 3"):
        g.compile().run({"n": 0, "items": []})
