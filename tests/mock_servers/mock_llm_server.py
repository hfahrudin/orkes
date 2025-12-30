from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import uvicorn
import json
import asyncio
from typing import Optional


app = FastAPI()

# --- Pydantic Models ---

class ChatCompletionRequest(BaseModel):
    model: str
    messages: list
    max_tokens: int = 1500
    stop: list = None
    temperature: float = 0.7
    stream: bool = False
    tools: Optional[list] = None

class CompletionRequest(BaseModel):
    model: str
    prompt: str
    max_tokens: int = 1500
    stop: list = None
    temperature: float = 0.7
    stream: bool = False

class GeminiRequest(BaseModel):
    contents: list
    stream: bool = False
    tools: Optional[list] = None

class ClaudeRequest(BaseModel):
    model: str
    messages: list
    max_tokens: int = 1500
    stream: bool = False

# --- OpenAI & vLLM ---

async def openai_stream_generator():
    response = {
        "id": "chatcmpl-123",
        "object": "chat.completion.chunk",
        "created": 1677652288,
        "model": "gpt-3.5-turbo",
        "choices": [{"delta": {"content": "Hello"}, "index": 0, "finish_reason": None}],
    }
    yield f"data: {json.dumps(response)}\n\n"
    await asyncio.sleep(0.1)
    response["choices"][0]["delta"]["content"] = " from"
    yield f"data: {json.dumps(response)}\n\n"
    await asyncio.sleep(0.1)
    response["choices"][0]["delta"]["content"] = " OpenAI/vLLM"
    yield f"data: {json.dumps(response)}\n\n"
    await asyncio.sleep(0.1)
    response["choices"][0]["delta"] = {}
    response["choices"][0]["finish_reason"] = "stop"
    yield f"data: {json.dumps(response)}\n\n"
    yield "data: [DONE]\n\n"


@app.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    if request.stream:
        return StreamingResponse(openai_stream_generator(), media_type="application/x-ndjson")
    
    if request.tools:
        return {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": request.model,
            "choices": [{
                "index": 0, 
                "message": {
                    "role": "assistant", 
                    "content": None,
                    "tool_calls": [{
                        "id": "call_123",
                        "type": "function",
                        "function": {
                            "name": "get_weather",
                            "arguments": "{\n  \"location\": \"San Francisco\"\n}"
                        }
                    }]
                }, 
                "finish_reason": "tool_calls"
            }],
            "usage": {"prompt_tokens": 9, "completion_tokens": 12, "total_tokens": 21},
        }
    else:
        await asyncio.sleep(0.1) # Simulate network delay
        user_message = ""
        if request.messages:
            user_message = request.messages[-1].get("content", "")

        return {
            "id": "chatcmpl-123",
            "object": "chat.completion",
            "created": 1677652288,
            "model": request.model,
            "choices": [{"index": 0, "message": {"role": "assistant", "content": "Hello from OpenAI/vLLM, how can I help you today?"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 9, "completion_tokens": 12, "total_tokens": 21},
        }

# --- Gemini ---

async def gemini_stream_generator():
    response = {
        "candidates": [{"content": {"parts": [{"text": "Hello"}], "role": "model"}, "finishReason": None, "index": 0}]
    }
    yield f"data: {json.dumps(response)}\n\n"
    await asyncio.sleep(0.1)
    response["candidates"][0]["content"]["parts"][0]["text"] = " from"
    yield f"data: {json.dumps(response)}\n\n"
    await asyncio.sleep(0.1)
    response["candidates"][0]["content"]["parts"][0]["text"] = " Gemini"
    yield f"data: {json.dumps(response)}\n\n"
    await asyncio.sleep(0.1)
    response["candidates"][0]["finishReason"] = "STOP"
    yield f"data: {json.dumps(response)}\n\n"

@app.post("/v1beta/models/{model}:generateContent")
async def generate_gemini_content(model: str, request: GeminiRequest):
    if request.tools:
        return {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "functionCall": {
                                    "name": "get_weather",
                                    "args": {
                                        "location": "San Francisco"
                                    }
                                }
                            }
                        ]
                    },
                    "finishReason": "TOOL_CODE",
                }
            ]
        }
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": "Hello from Gemini, how can I help you today?"}], "role": "model"},
                "finishReason": "STOP",
                "index": 0,
                "safetyRatings": [
                    {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "probability": "NEGLIGIBLE"},
                    {"category": "HARM_CATEGORY_HATE_SPEECH", "probability": "NEGLIGIBLE"},
                ],
            }
        ],
        "promptFeedback": {"safetyRatings": [{"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "probability": "NEGLIGIBLE"}]}
    }
    
@app.post("/v1beta/models/{model}:streamGenerateContent")
async def generate_gemini_content(model: str, request: GeminiRequest):
    return StreamingResponse(gemini_stream_generator(), media_type="application/x-ndjson")

# --- Claude ---

async def claude_stream_generator():
    yield f"data: {json.dumps({'type': 'message_start', 'message': {'id': 'msg-123', 'type': 'message', 'role': 'assistant', 'content': [], 'model': 'claude-3-opus-20240229', 'stop_reason': None, 'usage': {'input_tokens': 10, 'output_tokens': 1}}})}\n\n"
    await asyncio.sleep(0.1)
    yield f"data: {json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': 'Hello'}})}\n\n"
    await asyncio.sleep(0.1)
    yield f"data: {json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': ' from'}})}\n\n"
    await asyncio.sleep(0.1)
    yield f"data: {json.dumps({'type': 'content_block_delta', 'index': 0, 'delta': {'type': 'text_delta', 'text': ' Claude'}})}\n\n"
    await asyncio.sleep(0.1)
    yield f"data: {json.dumps({'type': 'message_delta', 'delta': {'stop_reason': 'end_turn', 'usage': {'output_tokens': 20}}})}\n\n"


@app.post("/v1/messages")
async def create_claude_message(request: ClaudeRequest):
    if request.stream:
        return StreamingResponse(claude_stream_generator(), media_type="application/x-ndjson")
    else:
        return {
            "id": "msg-123",
            "type": "message",
            "role": "assistant",
            "content": [{"type": "text", "text": "Hello from Claude, how can I help you today?"}],
            "model": request.model,
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 10, "output_tokens": 20},
        }


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
