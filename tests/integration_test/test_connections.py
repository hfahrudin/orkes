import subprocess
import time
import os
import pytest
from orkes.services.connections import LLMFactory

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