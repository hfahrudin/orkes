import pytest
from orkes.services.connectors import LLMFactory
from orkes.shared.schema import OrkesMessagesSchema, OrkesMessageSchema


# `mock_server` (the mock LLM server's URL) comes from conftest.py.

@pytest.mark.asyncio
async def test_openai_style_connection_with_schema(mock_server):
    vllm_client = LLMFactory.create_vllm(
        url=f"{mock_server}/v1", 
        model="meta-llama/Llama-2-7b-chat-hf"
    )
    
    messages = OrkesMessagesSchema(messages=[
        OrkesMessageSchema(role="user", content="Hello!")
    ])

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
async def test_gemini_connection_with_schema(mock_server):
    gemini_client = LLMFactory.create_gemini(
        api_key="test-key",
        model="gemini-pro",
        base_url=f"{mock_server}/v1beta"
    )
    
    messages = OrkesMessagesSchema(messages=[
        OrkesMessageSchema(role="user", content="Hello!")
    ])

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
async def test_anthropic_connection_with_schema(mock_server):
    anthropic_client = LLMFactory.create_anthropic(
        api_key="test-key",
        model="claude-3-opus-20240229",
        base_url=f"{mock_server}/v1"
    )
    
    messages = OrkesMessagesSchema(messages=[
        OrkesMessageSchema(role="user", content="Hello!")
    ])

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
