import pytest
from unittest.mock import Mock, AsyncMock
from typing import TypedDict, List, Dict, Callable
from orkes.agents.react import ReactAgent, ReactAgentState
from orkes.services.schema import LLMInterface
from orkes.shared.schema import OrkesToolSchema, ToolParameter, OrkesMessagesSchema, OrkesMessageSchema
import os

# --- Fixtures for Mocking ---

@pytest.fixture
def mock_llm_interface():
    """
    Fixture for a mock LLMInterface.
    """
    mock = Mock(spec=LLMInterface)
    # Configure the mock to return different responses based on the test scenario
    return mock

@pytest.fixture
def simple_tool():
    """
    Fixture for a simple mock tool.
    """
    # Mock the actual function to track its calls
    mock_my_function = Mock(return_value="Mocked processing result.")

    tool_schema = OrkesToolSchema(
        name="my_function",
        description="A simple function that processes a string.",
        parameters=ToolParameter(
            properties={"input_str": {"type": "string"}},
            required=["input_str"]
        ),
        function=mock_my_function # Use the mock here
    )
    return tool_schema

# --- Test Cases ---

def test_react_agent_direct_answer(mock_llm_interface, simple_tool):
    """
    Tests that the ReactAgent can get a direct answer from the LLM without tool use.
    """
    # Configure mock LLM to return a direct answer
    mock_llm_interface.send_message.return_value = {
        "content": {"content_type": "message", "content": "The direct answer is 42."},
        "raw": {} # Raw data can be empty for this test
    }
    
    agent = ReactAgent(llm=mock_llm_interface, tools=[simple_tool])
    response = agent.invoke("What is the meaning of life?")

    assert response == "The direct answer is 42."
    # Ensure LLM was called once
    mock_llm_interface.send_message.assert_called_once()
    # Ensure tool was not called
    assert not simple_tool.function.called

def test_react_agent_tool_use_and_answer(mock_llm_interface, simple_tool):
    """
    Tests that the ReactAgent can use a tool and then provide a final answer.
    """
    # Configure mock LLM to first request a tool call, then provide a final answer
    mock_llm_interface.send_message.side_effect = [
        # First LLM call: requests tool
        {
            "content": {"content_type": "tool_calls", "content": [{"function_name": "my_function", "arguments": {"input_str": "test input"}}]},
            "raw": {}
        },
        # Second LLM call: provides final answer after tool execution
        {
            "content": {"content_type": "message", "content": "Tool processed 'test input' and returned 'Processed: test input'."},
            "raw": {}
        }
    ]
    
    agent = ReactAgent(llm=mock_llm_interface, tools=[simple_tool])
    response = agent.invoke("Process 'test input' and give me the result.")

    assert "Tool processed 'test input' and returned 'Processed: test input'." in response
    # Ensure LLM was called twice
    assert mock_llm_interface.send_message.call_count == 2
    # Ensure tool was called once with the correct arguments
    simple_tool.function.assert_called_once_with(input_str="test input")

def test_react_agent_max_iterations(mock_llm_interface, simple_tool):
    """
    Tests that the ReactAgent stops after max_iterations if no answer is found.
    """
    # Configure mock LLM to continuously request a tool call
    mock_llm_interface.send_message.return_value = {
        "content": {"content_type": "tool_calls", "content": [{"function_name": "my_function", "arguments": {"input_str": "loop"}}]},
        "raw": {}
    }
    
    agent = ReactAgent(llm=mock_llm_interface, tools=[simple_tool])
    response = agent.invoke("Loop forever.", max_iterations=2) # Set max iterations to 2

    assert "Max iterations reached. Could not find an answer." in response
    # Ensure LLM was called max_iterations + 1 times
    assert mock_llm_interface.send_message.call_count == 3
    # Ensure tool was called max_iterations times
    assert simple_tool.function.call_count == 2

def test_react_agent_visualization(mock_llm_interface, simple_tool):
    """
    Tests that the ReactAgent generates trace and visualization files.
    """
    # Configure mock LLM to return a direct answer
    mock_llm_interface.send_message.return_value = {
        "content": {"content_type": "message", "content": "The direct answer is 42."},
        "raw": {}
    }

    agent = ReactAgent(llm=mock_llm_interface, tools=[simple_tool], trace_mode="all")
    agent.invoke("Generate a visualization.")

    trace_file = f"traces/trace_{agent.graph.run_id}.json"
    viz_file = f"traces/trace_{agent.graph.run_id}_inspector.html"

    try:
        assert os.path.exists(trace_file)
        assert os.path.exists(viz_file)
    finally:
        if os.path.exists(trace_file):
            os.remove(trace_file)
        if os.path.exists(viz_file):
            os.remove(viz_file)

