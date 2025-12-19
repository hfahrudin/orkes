from typing import Optional, Dict,List
import json
from orkes.services.schema import LLMProviderStrategy, ResponseSchema, ToolCallSchema

#TODO: STANDARIZED FOR STREAM
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

    def parse_response(self, response_data: Dict) -> ResponseSchema:
        try:
            message = response_data['choices'][0]['message']
            if 'tool_calls' in message and message['tool_calls']:
                tools_called = []
                for tool_call in message['tool_calls']:

                    tool_schema =  ToolCallSchema(function_name=tool_call['function']['name'],
                                                 arguments=json.loads(tool_call['function']['arguments']))
                    tools_called.append(tool_schema)
                return ResponseSchema(content_type="tool_calls", content=tools_called)
            return ResponseSchema(content_type="message", content=message['content'])
        
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
        
        try:
            # Anthropic path: content is a list of blocks
            content_blocks = response_data.get('content', [])
            
            tools_called = []
            text_parts = []

            for block in content_blocks:
                # 1. Check for Tool Use (Anthropic uses 'tool_use' type)
                if block.get('type') == 'tool_use':
                    tool_schema = ToolCallSchema(
                        name=block['name'],
                        arguments=block.get('input', {}), # Already a dict
                        id=block['id']                    # Anthropic ALWAYS provides a tool_use ID
                    )
                    tools_called.append(tool_schema)
                
                # 2. Check for Text blocks
                elif block.get('type') == 'text':
                    text_parts.append(block['text'])

            if tools_called:
                return ResponseSchema(content_type="tool_calls", content=tools_called)
            
            # Join all text blocks if there were multiple
            full_text = "\n".join(text_parts)
            return ResponseSchema(content_type="message", content=full_text)

        except (KeyError, IndexError):
            raise ValueError(f"Unexpected Anthropic response format: {response_data}")

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
            # Gemini path: candidates[0] -> content -> parts
            candidate = response_data['candidates'][0]
            parts = candidate.get('content', {}).get('parts', [])
            
            tools_called = []
            text_content = ""

            for part in parts:
                # 1. Check for Function Calls (Gemini uses 'functionCall' and 'args')
                if 'functionCall' in part:
                    fc = part['functionCall']
                    tool_schema = ToolCallSchema(
                        function_name=fc['name'],
                        arguments=fc.get('args', {}) # Already a dict, no json.loads needed
                    )
                    tools_called.append(tool_schema)
                
                # 2. Check for Text (In case of mixed response or plain message)
                elif 'text' in part:
                    text_content += part['text']

            if tools_called:
                return ResponseSchema(content_type="tool_calls", content=tools_called)
            
            return ResponseSchema(content_type="message", content=text_content)

        except (KeyError, IndexError):
            raise ValueError(f"Unexpected Gemini response format: {response_data}")

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
