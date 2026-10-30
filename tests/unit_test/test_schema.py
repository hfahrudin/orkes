"""Tests for the schema dataclasses that replaced pydantic models."""
import json
import threading
from typing import TypedDict

import pytest

from orkes.graph.core import OrkesGraph
from orkes.services.strategies import OpenAIStyleStrategy, AnthropicStrategy, GoogleGeminiStrategy
from orkes.shared.schema import (
    OrkesMessageSchema,
    OrkesMessagesSchema,
    OrkesToolSchema,
    ToolParameter,
    to_dict,
)
from orkes.shared.utils import callable_to_orkes_tool_schema


# --- Messages ---------------------------------------------------------------

def test_messages_accept_plain_dicts():
    """The docs build messages from dicts; they must become message objects."""
    messages = OrkesMessagesSchema(messages=[{"role": "user", "content": "hi"}])
    msg = messages.messages[0]
    assert isinstance(msg, OrkesMessageSchema)
    assert (msg.role, msg.content, msg.content_type, msg.tool_call_id) == ("user", "hi", None, None)


def test_message_missing_field_raises():
    with pytest.raises(TypeError):
        OrkesMessageSchema(role="user")
    with pytest.raises(TypeError):
        OrkesMessagesSchema(messages=[{"role": "user"}])
    with pytest.raises(TypeError):
        OrkesMessagesSchema()


def test_message_role_must_be_str():
    with pytest.raises(TypeError, match="role"):
        OrkesMessageSchema(role=1, content="hi")


def test_message_fields_are_keyword_only():
    with pytest.raises(TypeError):
        OrkesMessageSchema("user", "hi")


# --- Tools ------------------------------------------------------------------

def _weather_tool():
    def get_weather(city: str) -> str:
        """Get the weather.

        Args:
            city (str): The city.
        """
        return "sunny"
    return get_weather


def test_tool_accepts_dict_parameters():
    tool = OrkesToolSchema(name="t", description="d", parameters={"properties": {"x": {"type": "string"}}})
    assert isinstance(tool.parameters, ToolParameter)
    assert tool.parameters.type == "object"


@pytest.mark.parametrize("strategy", [OpenAIStyleStrategy(), AnthropicStrategy(), GoogleGeminiStrategy()])
def test_tool_payloads_are_json_and_exclude_callable(strategy):
    """The tool's Python function must never be sent to the provider."""
    tool = callable_to_orkes_tool_schema(_weather_tool())
    tool.function = _weather_tool()
    payload = strategy.get_tools_payload([tool])
    text = json.dumps(payload)  # raises if a callable slipped in
    assert "get_weather" in text
    assert '"function": null' not in text


def test_openai_tool_payload_shape():
    tool = callable_to_orkes_tool_schema(_weather_tool())
    [payload] = OpenAIStyleStrategy().get_tools_payload([tool])
    assert payload["type"] == "function"
    assert payload["function"]["name"] == "get_weather"
    assert payload["function"]["parameters"]["properties"]["city"]["type"] == "string"
    assert "function" not in payload["function"]


@pytest.mark.parametrize("strategy", [OpenAIStyleStrategy(), AnthropicStrategy(), GoogleGeminiStrategy()])
def test_message_payloads_are_json(strategy):
    messages = OrkesMessagesSchema(messages=[
        {"role": "system", "content": "be brief"},
        {"role": "user", "content": "hi"},
    ])
    json.dumps(strategy.get_messages_payload(messages))


# --- to_dict ----------------------------------------------------------------

def test_to_dict_converts_nested_objects():
    messages = OrkesMessagesSchema(messages=[{"role": "user", "content": "hi"}])
    assert to_dict(messages) == {
        "messages": [{"role": "user", "content": "hi", "content_type": None, "tool_call_id": None}]
    }


def test_to_dict_does_not_copy_values():
    """State can hold objects that can't be copied, like locks."""
    lock = threading.Lock()
    tool = OrkesToolSchema(name="t", description="d", parameters={"properties": {}}, function=lock)
    assert to_dict(tool)["function"] is lock
    assert "function" not in to_dict(tool, exclude=("function",))


# --- Trace format (relied on by orkes-watcher) ---------------------------------

class S(TypedDict):
    n: int


def test_trace_json_keeps_its_fields():
    """The saved trace's field names are a contract with orkes-watcher."""
    def node(s: S):
        return s

    g = OrkesGraph(S)
    g.add_node("node", node)
    g.add_edge(g.START, "node")
    g.add_edge("node", g.END)
    runner = g.compile()
    runner.run({"n": 0})

    trace = json.loads(json.dumps(to_dict(runner.trace), default=str))
    assert set(trace) == {
        "graph_name", "graph_description", "run_id", "start_time", "elapsed_time",
        "status", "nodes_trace", "edges_trace", "error", "failed_node", "final_state",
    }
    assert set(trace["nodes_trace"][0]) == {"node_name", "node_id", "node_description", "meta"}
    assert set(trace["edges_trace"][0]) == {
        "edge_id", "edge_run_number", "from_node", "to_node", "passes_left", "edge_type",
        "elapsed", "state_snapshot", "meta", "function_traces", "llm_traces", "error",
        "started_at", "node_elapsed",
    }
