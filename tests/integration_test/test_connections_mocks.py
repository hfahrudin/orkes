import subprocess
import time
import os
import pytest
import json
from orkes.services.connectors import LLMFactory
from orkes.shared.schema import OrkesMessagesSchema, OrkesMessageSchema

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
    
    messages = OrkesMessagesSchema(messages=[OrkesMessageSchema(role="user", content="Hello!")])

    # Test send
    response = vllm_client.send_message(messages)
    result = response['content']
    content_type = result.get("content_type")
    content = result.get("content")
    assert content_type == "message"
    assert "Hello from OpenAI/vLLM" in content

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
    
    messages = OrkesMessagesSchema(messages = [{"role": "user", "content": "Say 'hello' in 5 words."}])

    # Test send
    response = gemini_client.send_message(messages)
    result = response['content']
    content_type = result.get("content_type")
    content = result.get("content")
    assert content_type == "message"
    assert "Hello from Gemini" in content
  
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
    
    messages = OrkesMessagesSchema(messages = [{"role": "user", "content": "Say 'hello' in 5 words."}])

    # Test send
    response = anthropic_client.send_message(messages)
    result = response['content']
    content_type = result.get("content_type")
    content = result.get("content")
    assert content_type == "message"
    assert "Hello from Claude" in content

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
    
    messages = OrkesMessagesSchema(messages = [{"role": "user", "content": "What is the weather in San Francisco?"}])
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
    
    result = response['content']
    content_type = result.get("content_type")
    content = result.get("content")
    assert content_type == "tool_calls", f"Expected content_type 'tool_calls', got '{content_type}'"
    tool_call = content[0]
    tool_name = tool_call["function_name"]
    tool_arguments = tool_call["arguments"]

    assert tool_name == "get_weather"
    assert "San Francisco" in str(tool_arguments)

@pytest.mark.asyncio
async def test_gemini_tool_calling_mock(mock_server):
    gemini_client = LLMFactory.create_gemini(
        api_key="test-key",
        model="gemini-pro",
        base_url=f"{mock_server}/v1beta"
    )
    
    messages = OrkesMessagesSchema(messages = [{"role": "user", "content": "What is the weather in San Francisco?"}])
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
    
    result = response['content']
    content_type = result.get("content_type")
    content = result.get("content")
    assert content_type == "tool_calls", f"Expected content_type 'tool_calls', got '{content_type}'"
    tool_call = content[0]
    tool_name = tool_call["function_name"]
    tool_arguments = tool_call["arguments"]

    assert tool_name == "get_weather"
    assert "San Francisco" in str(tool_arguments)
