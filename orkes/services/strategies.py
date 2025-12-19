from abc import ABC, abstractmethod
from typing import Optional, Dict, AsyncGenerator, Any, List
import json


class LLMProviderStrategy(ABC):
    """
    Strategy interface for handling provider-specific logic.
    Responsible for payload structure and parsing responses.
    """
    
    @abstractmethod
    def prepare_payload(self, model: str, messages: List[Dict[str, str]], stream: bool, settings: Dict, tools: Optional[List[Dict]] = None) -> Dict:
        """Convert standard messages to provider-specific JSON payload."""
        pass

    @abstractmethod
    def parse_response(self, response_data: Dict) -> str:
        """Extract text content from a non-streaming response."""
        pass

    @abstractmethod
    def parse_stream_chunk(self, chunk: str) -> Optional[str]:
        """Extract text content from a streaming chunk line."""
        pass
    
    @abstractmethod
    def get_headers(self, api_key: str) -> Dict[str, str]:
        """Return authentication headers."""
        pass



class OpenAIStyleStrategy(LLMProviderStrategy):
    """
    Handles OpenAI, vLLM, DeepSeek, and other compatible APIs.
    """
    def get_headers(self, api_key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def prepare_payload(self, model: str, messages: List, stream: bool, settings: Dict, tools: Optional[List[Dict]] = None) -> Dict:
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            **settings
        }
        if tools:
            payload['tools'] = tools
        return payload

    def parse_response(self, response_data: Dict) -> str:
        try:
            message = response_data['choices'][0]['message']
            if 'tool_calls' in message and message['tool_calls']:
                return json.dumps({
                    "tool_calls": message['tool_calls']
                })
            return message['content']
        except (KeyError, IndexError):
            raise ValueError(f"Unexpected response format: {response_data}")

    def parse_stream_chunk(self, line: str) -> Optional[str]:
        if not line.startswith("data: "):
            return None
        data_str = line[6:]  # Strip 'data: '
        if data_str.strip() == "[DONE]":
            return None
        try:
            data = json.loads(data_str)
            delta = data['choices'][0]['delta']
            return delta.get('content', '')
        except json.JSONDecodeError:
            return None

#TODO: validate first
class AnthropicStrategy(LLMProviderStrategy):
    """Handles Claude / Anthropic specific API formats."""
    def get_headers(self, api_key: str) -> Dict[str, str]:
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

    def prepare_payload(self, model: str, messages: List, stream: bool, settings: Dict, tools: Optional[List[Dict]] = None) -> Dict:
        # Anthropic requires 'system' to be top-level, separate from 'messages'
        system_msg = next((msg['content'] for msg in messages if msg['role'] == 'system'), None)
        chat_messages = [msg for msg in messages if msg['role'] != 'system']
        
        payload = {
            "model": model,
            "messages": chat_messages,
            "stream": stream,
            **settings
        }
        if system_msg:
            payload["system"] = system_msg
        
        if tools:
            payload["tools"] = tools

        return payload

    def parse_response(self, response_data: Dict) -> str:
        
        # Check for tool use
        tool_use_block = next((block for block in response_data['content'] if block['type'] == 'tool_use'), None)
        if tool_use_block:
            return json.dumps({
                "tool_calls": [{
                    "id": tool_use_block['id'],
                    "type": "function",
                    "function": {
                        "name": tool_use_block['name'],
                        "arguments": json.dumps(tool_use_block['input'])
                    }
                }]
            })
        
        return response_data['content'][0]['text']

    def parse_stream_chunk(self, line: str) -> Optional[str]:
        if not line.startswith("data: "):
            return None
        try:
            data = json.loads(line[6:])
            if data['type'] == 'content_block_delta':
                return data['delta'].get('text', '')
            return None
        except:
            return None

class GoogleGeminiStrategy(LLMProviderStrategy):
    """Handles Google Gemini REST API formats."""
    def get_headers(self, api_key: str) -> Dict[str, str]:
        # Google often passes API key via query param, but can use header for some setups.
        # This implementation assumes standard REST approach; SDK use is usually preferred for Google.
        return {
            'X-goog-api-key': api_key,
            "Content-Type": "application/json"
        }

    def prepare_payload(self, model: str, messages: List, stream: bool, settings: Dict, tools: Optional[List[Dict]] = None) -> Dict:
        # Simplistic mapping to Google's "contents" format
        gemini_contents = []
        for msg in messages:
            role = "user" if msg['role'] == "user" else "model"
            gemini_contents.append({
                "role": role,
                "parts": [{"text": msg['content']}]
            })

        if "max_tokens" in settings:
            settings["max_output_tokens"] = settings.pop("max_tokens")

        payload = {
            "contents": gemini_contents,
            "generation_config": settings
        }

        if tools:
            payload['tools'] = tools

        return payload


    def parse_response(self, response_data: Dict) -> str:
        try:
            candidate = response_data['candidates'][0]
            if 'content' in candidate and 'parts' in candidate['content']:
                parts = candidate['content']['parts']
                # Check for function call
                function_call_part = next((part for part in parts if 'functionCall' in part), None)
                if function_call_part:
                     # Adapt to OpenAI's 'tool_calls' structure
                    return json.dumps({
                        "tool_calls": [{
                            "id": "null",
                            "type": "function",
                            "function": {
                                "name": function_call_part['functionCall']['name'],
                                "arguments": json.dumps(function_call_part['functionCall']['args'])
                            }
                        }]
                    })
                
                # Fallback to text
                text_part = next((part['text'] for part in parts if 'text' in part), None)
                if text_part:
                    return text_part

            return "" # Should not be reached if response is valid
        except (KeyError, IndexError):
            return ""

    def parse_stream_chunk(self, line: str) -> Optional[str]:
        if not line.startswith("data: "):
            return None
        data_str = line[6:]
        if not data_str:
            return None
        try:
            data = json.loads(data_str)
            return data['candidates'][0]['content']['parts'][0]['text']
        except (json.JSONDecodeError, KeyError, IndexError):
            return None
