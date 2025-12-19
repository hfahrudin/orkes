import os
import pytest
import json
from orkes.services.connectors import LLMFactory

from dotenv import load_dotenv


@pytest.mark.asyncio
async def test_openai_api_stream_send_with_env_key():
    """
    Test actual OpenAI API stream and send functionality using OPENAI_API_KEY from .env or environment variables.
    This test will be skipped if OPENAI_API_KEY is not found.
    """
    load_dotenv() # Load environment variables from .env file

    openai_api_key = os.getenv("OPENAI_API_KEY")

    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not found in .env or environment variables. Skipping real OpenAI API test.")

    try:
        # Use a dummy model for testing if a real one is not specified, or use the default
        # Assuming LLMFactory.create_openai uses default models or allows overriding

        openai_client = LLMFactory.create_openai(api_key=openai_api_key)
        
        messages = [{"role": "user", "content": "Say 'hello' in 5 words."}]

        # Test send functionality
        send_response = openai_client.send_message(messages)
        assert send_response is not None
        reply = send_response.get('raw', {}) \
            .get('choices', [{}])[0] \
            .get('message', {}) \
            .get('content')
        assert isinstance(reply, str)
        print(f"OpenAI send response: {send_response.get('content')}")

        # Test stream functionality
        stream_response_generator = openai_client.stream_message(messages)
        full_content = ""
        async for chunk in stream_response_generator:
            full_content += chunk
        assert full_content is not None
        assert isinstance(full_content, str)
        print(f"OpenAI stream response: {full_content}")

    except Exception as e:
        pytest.fail(f"Real OpenAI API test failed: {e}")



@pytest.mark.asyncio
async def test_gemini_api_stream_send_with_env_key():
    """
    Test actual GEMINI API stream and send functionality using GEMINI_API_KEY from .env or environment variables.
    This test will be skipped if GEMINI_API_KEY is not found.
    """
    load_dotenv() # Load environment variables from .env file

    gemini_api_key = os.getenv("GEMINI_API_KEY")

    if not gemini_api_key:
        pytest.skip("GEMINI_API_KEY not found in .env or environment variables. Skipping real OpenAI API test.")

    try:

        gemini_client = LLMFactory.create_gemini(api_key=gemini_api_key)
        
        messages = [{"role": "user", "content": "Say 'hello' in 5 words."}]

        # Test send functionality
        send_response = gemini_client.send_message(messages)
        assert send_response is not None
        reply = send_response['raw']['candidates'][0]['content']['parts'][0]['text']
        assert isinstance(reply, str)
        print(f"Gemini send response: {send_response.get('content')}")

        # Test stream functionality
        stream_response_generator = gemini_client.stream_message(messages)
        full_content = ""
        async for chunk in stream_response_generator:
            full_content += chunk
        assert full_content is not None
        assert isinstance(full_content, str)
        print(f"Gemini stream response: {full_content}")

    except Exception as e:
        pytest.fail(f"Real Gemini API test failed: {e}")


@pytest.mark.asyncio
async def test_openai_with_tool_calling_live():
    """
    Test actual OpenAI API with tool calling functionality.
    This test will be skipped if OPENAI_API_KEY is not found.
    """
    load_dotenv()
    openai_api_key = os.getenv("OPENAI_API_KEY")
    if not openai_api_key:
        pytest.skip("OPENAI_API_KEY not found. Skipping real OpenAI API test.")

    openai_client = LLMFactory.create_openai(api_key=openai_api_key)
    
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

    response = openai_client.send_message(messages, tools=tools)
    
    tool_calls = json.loads(response['content'])
    assert tool_calls.get("tool_calls") is not None
    tool_call = tool_calls["tool_calls"][0]
    tool_arg = tool_call["function"]["arguments"]
    print("Expected tool call: get_weather | Expected argument: San Francisco")
    print(f"Returned tool call: {tool_call} | Expected argument:{tool_arg}")
    assert tool_call["function"]["name"] == "get_weather"
    assert "San Francisco" in tool_call["function"]["arguments"]


@pytest.mark.asyncio
async def test_gemini_with_tool_calling_live():
    """
    Test actual Gemini API with tool calling functionality.
    This test will be skipped if GEMINI_API_KEY is not found.
    """
    load_dotenv()
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if not gemini_api_key:
        pytest.skip("GEMINI_API_KEY not found. Skipping real Gemini API test.")

    gemini_client = LLMFactory.create_gemini(api_key=gemini_api_key)
    
    messages = [{"role": "user", "content": "What is the weather in San Francisco?"}]
    tools = [{
        "function_declarations": [
            {
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
            }
        ]
    }]
    
    response = gemini_client.send_message(messages, tools=tools)
    
    tool_calls = json.loads(response['content'])
    assert tool_calls.get("tool_calls") is not None
    tool_call = tool_calls["tool_calls"][0]
    tool_arg = tool_call["function"]["arguments"]
    print("Expected tool call: get_weather | Expected argument: San Francisco")
    print(f"Returned tool call: {tool_call} | Expected argument:{tool_arg}")
    assert tool_call["function"]["name"] == "get_weather"
    assert "San Francisco" in tool_call["function"]["arguments"]
