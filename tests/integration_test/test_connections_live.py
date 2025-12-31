import os
import pytest
import json
from orkes.services.connectors import LLMFactory
from orkes.shared.schema import OrkesMessagesSchema, OrkesToolSchema
from jsonschema import validate

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
        
        messages = OrkesMessagesSchema(messages = [{"role": "user", "content": "Say 'hello' in 5 words."}])

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
        
        messages = OrkesMessagesSchema(messages = [{"role": "user", "content": "Say 'hello' in 5 words."}])

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
    
    messages = OrkesMessagesSchema(messages = [{"role": "user", "content": "What is the weather in San Francisco?"}])
    # tools = [{
    #         "type": "function",
    #         "function": {
    #             "name": "get_weather",
    #             "description": "Get the current weather in a given location",
    #             "parameters": {
    #                 "type": "object",
    #                 "properties": {
    #                     "location": {
    #                         "type": "string",
    #                         "description": "The city and state, e.g. San Francisco, CA",
    #                     },
    #                 },
    #                 "required": ["location"],
    #             }
    #         }
    #     }]
    
    def get_weather(location: str):
        """
        Get the current weather in a given location

        Args:
            location: The city and state, e.g. San Francisco, CA
        """
        # Your logic here
        return f"The weather in {location} is sunny."

    
    # actual_tool_payloads = openai_client.provider.get_tools_payload([orkes_tool])
    # assert actual_tool_payloads == tools, "Tool payload schema does not match expected format."

    response = openai_client.send_message(messages, tools=[get_weather])
    
    result = response['content']
    content_type = result.get("content_type")
    content = result.get("content")
    print(content)
    assert content_type == "tool_calls", f"Expected content_type 'tool_calls', got '{content_type}'"
    tool_call = content[0]
    tool_name = tool_call["function_name"]
    tool_arguments = tool_call["arguments"]
    print("Expected tool call: get_weather | Expected argument: location-San Francisco")
    print(f"Returned tool call: {tool_name} | Expected argument:{tool_arguments}")
    assert tool_name == "get_weather"
    assert "San Francisco" in str(tool_arguments)


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
    
    messages = OrkesMessagesSchema(messages = [{"role": "user", "content": "What is the weather in San Francisco?"}])
    # tools = [{
    #     "function_declarations": [
    #         {
    #             "name": "get_weather",
    #             "description": "Get the current weather in a given location",
    #             "parameters": {
    #                 "type": "object",
    #                 "properties": {
    #                     "location": {
    #                         "type": "string",
    #                         "description": "The city and state, e.g. San Francisco, CA",
    #                     },
    #                 },
    #                 "required": ["location"],
    #             },
    #         }
    #     ]
    # }]
    
    orkes_tool = OrkesToolSchema(name="get_weather",
                                    description="Get the current weather in a given location",
                                    parameters={
                                        "type": "object",
                                        "properties": {
                                            "location": {
                                                "type": "string",
                                                "description": "The city and state, e.g. San Francisco, CA",
                                            },
                                        },
                                        "required": ["location"],
                                    })
    
    # actual_tool_payloads = gemini_client.provider.get_tools_payload([orkes_tool])
    # print("here: ", actual_tool_payloads)
    # assert actual_tool_payloads == tools, "Tool payload schema does not match expected format."
    response = gemini_client.send_message(messages, tools=[orkes_tool])
    
    result = response['content']
    content_type = result.get("content_type")
    content = result.get("content")
    assert content_type == "tool_calls", f"Expected content_type 'tool_calls', got '{content_type}'"
    tool_call = content[0]
    tool_name = tool_call["function_name"]
    tool_arguments = tool_call["arguments"]
    print("Expected tool call: get_weather | Expected argument: location-San Francisco")
    print(f"Returned tool call: {tool_name} | Expected argument:{tool_arguments}")
    assert tool_name == "get_weather"
    assert "San Francisco" in str(tool_arguments)
