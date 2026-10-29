import requests
import json

# `mock_server` (the mock LLM server's URL) comes from conftest.py.


def test_openai_chat_completions_streaming(mock_server):
    response = requests.post(
        f"{mock_server}/v1/chat/completions",
        json={
            "model": "gpt-3.5-turbo",
            "messages": [{"role": "user", "content": "Hello!"}],
            "stream": True,
        },
        stream=True
    )
    assert response.status_code == 200
    full_content = ""
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data: '):
                json_str = decoded_line[6:]
                if json_str == "[DONE]":
                    break
                data = json.loads(json_str)
                if 'content' in data['choices'][0]['delta']:
                    full_content += data['choices'][0]['delta']['content']
    assert "Hello from OpenAI/vLLM" in full_content


def test_gemini_generate_content_streaming(mock_server):
    response = requests.post(
        f"{mock_server}/v1beta/models/gemini-pro:streamGenerateContent",
        json={"contents": [{"parts": [{"text": "Hello!"}]}]},
        stream=True
    )
    assert response.status_code == 200
    full_content = ""
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data: '):
                json_str = decoded_line[6:]
                if json_str == "[DONE]":
                    break
                data = json.loads(json_str)
                if 'parts' in data['candidates'][0]['content']:
                    full_content += data['candidates'][0]['content']['parts'][0]['text']

    assert "Hello from Gemini" in full_content


def test_claude_messages_streaming(mock_server):
    response = requests.post(
        f"{mock_server}/v1/messages",
        json={
            "model": "claude-3-opus-20240229",
            "messages": [{"role": "user", "content": "Hello!"}],
            "max_tokens": 1024,
            "stream": True
        },
        stream=True
    )
    assert response.status_code == 200
    full_content = ""
    for line in response.iter_lines():
        if line:
            decoded_line = line.decode('utf-8')
            if decoded_line.startswith('data: '):
                json_str = decoded_line[6:]
                if not json_str:
                    continue
                data = json.loads(json_str)
                if data['type'] == 'content_block_delta':
                    full_content += data['delta']['text']

    assert "Hello from Claude" in full_content
