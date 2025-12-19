import subprocess
import time
import os
import pytest
import json
from orkes.services.connectors import LLMFactory

from dotenv import load_dotenv

@pytest.fixture(scope="module")
def mock_server():
    # Start the mock server in a separate process
    mock_server_path = os.path.join(os.path.dirname(__file__), '..', 'mock_servers', 'mock_llm_server.py')
    server_process = subprocess.Popen(['python', mock_server_path])

    # Give the server a moment to start
    time.sleep(5)

    yield "http://localhost:8000"

    # Terminate the mock server process
    server_process.terminate()
    server_process.wait()

@pytest.mark.asyncio
async def test_openai_style_connection(mock_server):
    vllm_client = LLMFactory.create_vllm(
        url=f"{mock_server}/v1", 
        model="meta-llama/Llama-2-7b-chat-hf"
    )
    
    messages = [{"role": "user", "content": "Hello!"}]

    # Test send
    response = vllm_client.send_message(messages)
    assert "Hello from OpenAI/vLLM" in response['content']

    # Test stream
    stream_response = vllm_client.stream_message(messages)
    full_content = ""
    async for chunk in stream_response:
        full_content += chunk
    assert "Hello from OpenAI/vLLM" in full_content

@pytest.mark.asyncio
async def test_gemini_connection(mock_server):
    gemini_client = LLMFactory.create_gemini(
        api_key="test-key",
        model="gemini-pro",
        base_url=f"{mock_server}/v1beta"
    )
    
    messages = [{"role": "user", "content": "Hello!"}]

    # Test send
    response = gemini_client.send_message(messages)
    assert "Hello from Gemini" in response['content']
  
    # Test stream
    stream_response = gemini_client.stream_message(messages)
    full_content = ""
    async for chunk in stream_response:
        full_content += chunk
    assert "Hello from Gemini" in full_content

@pytest.mark.asyncio
async def test_anthropic_connection(mock_server):
    anthropic_client = LLMFactory.create_anthropic(
        api_key="test-key",
        model="claude-3-opus-20240229",
        base_url=f"{mock_server}/v1"
    )
    
    messages = [{"role": "user", "content": "Hello!"}]

    # Test send
    response = anthropic_client.send_message(messages)
    assert "Hello from Claude" in response['content']

    # Test stream
    stream_response = anthropic_client.stream_message(messages)
    full_content = ""
    async for chunk in stream_response:
        full_content += chunk
    assert "Hello from Claude" in full_content


@pytest.mark.asyncio
async def test_openai_style_tool_calling_mock(mock_server):
    vllm_client = LLMFactory.create_vllm(
        url=f"{mock_server}/v1", 
        model="meta-llama/Llama-2-7b-chat-hf"
    )
    
    messages = [{"role": "user", "content": "What is the weather in San Francisco?"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                        },
                    },
                    "required": ["location"],
                },
            },
        }
    ]

    response = vllm_client.send_message(messages, tools=tools)
    
    tool_calls = json.loads(response['content'])
    assert tool_calls.get("tool_calls") is not None
    tool_call = tool_calls["tool_calls"][0]
    assert tool_call["function"]["name"] == "get_weather"
    assert "San Francisco" in tool_call["function"]["arguments"]


@pytest.mark.asyncio
async def test_gemini_tool_calling_mock(mock_server):
    gemini_client = LLMFactory.create_gemini(
        api_key="test-key",
        model="gemini-pro",
        base_url=f"{mock_server}/v1beta"
    )
    
    messages = [{"role": "user", "content": "What is the weather in San Francisco?"}]
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "Get the current weather in a given location",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "The city and state, e.g. San Francisco, CA",
                        },
                    },
                    "required": ["location"],
                },
            },
        }
    ]

    response = gemini_client.send_message(messages, tools=tools)
    
    tool_calls = json.loads(response['content'])
    assert tool_calls.get("tool_calls") is not None
    tool_call = tool_calls["tool_calls"][0]
    assert tool_call["function"]["name"] == "get_weather"
    assert "San Francisco" in tool_call["function"]["arguments"]
