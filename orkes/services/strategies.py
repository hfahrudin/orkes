from typing import Optional, Dict,List
import json
from orkes.services.schema import LLMProviderStrategy, RequestSchema, ToolCallSchema
from typing import Optional, Dict,List, Union
from orkes.shared.schema import OrkesMessagesSchema, OrkesToolSchema

#TODO: STANDARIZED FOR STREAM
class OpenAIStyleStrategy(LLMProviderStrategy):
    """
    A strategy for interacting with LLM providers that follow the OpenAI API format.
    This includes providers like OpenAI, vLLM, DeepSeek, and other compatible APIs.
    """
    def get_headers(self, api_key: str) -> Dict[str, str]:
        """
        Returns the headers required for authentication with an OpenAI-style API.
        """
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }

    def get_messages_payload(self, messages: OrkesMessagesSchema) -> Dict[str, List[Dict]]:
        """
        Converts an OrkesMessagesSchema into the format expected by an OpenAI-style API.
        """
        processed_messages = [msg.model_dump() for msg in messages.messages]
        return {"messages": processed_messages}
    
    def get_tools_payload(self, tools: List[OrkesToolSchema]) -> List[Dict]:
        """
        Converts a list of OrkesToolSchema objects into the format expected by an
        OpenAI-style API.
        """
        tool_payloads = [{
                "type": "function",
                "function": tool.model_dump()
            } for tool in tools]
        return tool_payloads

    def prepare_payload(self, model: str, messages: OrkesMessagesSchema, stream: bool, settings: Dict, tools: Optional[List[OrkesToolSchema]] = None) -> Dict:
        """
        Prepares the full payload for a request to an OpenAI-style API.
        """
        message_payload = self.get_messages_payload(messages)
        payload = {
            "model": model,
            "stream": stream,
            **settings,
            **message_payload
        }
        if tools:
            payload['tools'] = self.get_tools_payload(tools)
        return payload

    def parse_response(self, response_data: Dict) -> RequestSchema:
        """
        Parses a response from an OpenAI-style API.
        """
        try:
            message = response_data['choices'][0]['message']
            if 'tool_calls' in message and message['tool_calls']:
                tools_called = []
                for tool_call in message['tool_calls']:
                    tool_schema = ToolCallSchema(
                        function_name=tool_call['function']['name'],
                        arguments=json.loads(tool_call['function']['arguments'])
                    )
                    tools_called.append(tool_schema)
                return RequestSchema(content_type="tool_calls", content=tools_called)
            return RequestSchema(content_type="message", content=message['content'])
        
        except (KeyError, IndexError):
            raise ValueError(f"Unexpected response format: {response_data}")

    def parse_stream_chunk(self, line: str) -> Optional[str]:
        """
        Parses a single chunk of a streaming response from an OpenAI-style API.
        """
        if not line.startswith("data: "):
            return None
        data_str = line[6:]
        if data_str.strip() == "[DONE]":
            return None
        try:
            data = json.loads(data_str)
            delta = data['choices'][0]['delta']
            return delta.get('content', '')
        except json.JSONDecodeError:
            return None

class AnthropicStrategy(LLMProviderStrategy):
    """
    A strategy for interacting with the Anthropic API (Claude).
    """
    def get_headers(self, api_key: str) -> Dict[str, str]:
        """
        Returns the headers required for authentication with the Anthropic API.
        """
        return {
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }

    def get_messages_payload(self, messages: OrkesMessagesSchema) -> Dict[str, Union[str, List[Dict]]]:
        """
        Converts an OrkesMessagesSchema into the format expected by the Anthropic API.
        """
        processed_messages = [msg.model_dump() for msg in messages.messages]

        # Anthropic requires 'system' to be a top-level parameter.
        system_msg = next((msg['content'] for msg in processed_messages if msg['role'] == 'system'), None)
        chat_messages = [msg for msg in processed_messages if msg['role'] != 'system']

        message_payload = {"messages": chat_messages}
        if system_msg:
            message_payload["system"] = system_msg
        
        return message_payload
    
    def get_tools_payload(self, tools: List[OrkesToolSchema]) -> List[Dict]:
        """
        Converts a list of OrkesToolSchema objects into the format expected by the
        Anthropic API.
        """
        tool_payloads = [{
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters.model_dump()
            }
            for tool in tools]
        return tool_payloads

    def prepare_payload(self, model: str, messages: OrkesMessagesSchema, stream: bool, settings: Dict, tools: Optional[List[OrkesToolSchema]] = None) -> Dict:
        """
        Prepares the full payload for a request to the Anthropic API.
        """
        message_payload = self.get_messages_payload(messages)
        
        payload = {
            "model": model,
            "stream": stream,
            **settings,
            **message_payload
        }
        
        if tools:
            payload["tools"] = self.get_tools_payload(tools)

        return payload

    def parse_response(self, response_data: Dict) -> RequestSchema:
        """
        Parses a response from the Anthropic API.
        """
        try:
            content_blocks = response_data.get('content', [])
            
            tools_called = []
            text_parts = []

            for block in content_blocks:
                if block.get('type') == 'tool_use':
                    tool_schema = ToolCallSchema(
                        function_name=block['name'],
                        arguments=block.get('input', {}),
                    )
                    tools_called.append(tool_schema)
                
                elif block.get('type') == 'text':
                    text_parts.append(block['text'])

            if tools_called:
                return RequestSchema(content_type="tool_calls", content=tools_called)
            
            full_text = "\n".join(text_parts)
            return RequestSchema(content_type="message", content=full_text)

        except (KeyError, IndexError):
            raise ValueError(f"Unexpected Anthropic response format: {response_data}")

    def parse_stream_chunk(self, line: str) -> Optional[str]:
        """
        Parses a single chunk of a streaming response from the Anthropic API.
        """
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
    """
    A strategy for interacting with the Google Gemini REST API.
    """
    def get_headers(self, api_key: str) -> Dict[str, str]:
        """
        Returns the headers required for authentication with the Google Gemini API.
        """
        return {
            'X-goog-api-key': api_key,
            "Content-Type": "application/json"
        }

    def get_messages_payload(self, messages: OrkesMessagesSchema) -> Dict[str, List[Dict]]:
        """
        Converts an OrkesMessagesSchema into the format expected by the Google Gemini API.
        """
        processed_messages = [msg.model_dump() for msg in messages.messages]

        gemini_contents = []
        for msg in processed_messages:
            role = "user" if msg['role'] == "user" else "model"
            gemini_contents.append({
                "role": role,
                "parts": [{"text": msg['content']}]
            })
        return {"contents": gemini_contents}

    def get_tools_payload(self, tools: List[OrkesToolSchema]) -> List[Dict]:
        """
        Converts a list of OrkesToolSchema objects into the format expected by the
        Google Gemini API.
        """
        tools_payloads = []
        for tool in tools:
            dump = tool.model_dump()
            tool_dict = {
                "name": dump["name"],
                "description": dump["description"],
                "parameters": dump["parameters"]
            }
            tools_payloads.append(tool_dict)    
        return [{"function_declarations" : tools_payloads}]

    def prepare_payload(self, model: str, messages: OrkesMessagesSchema, stream: bool, settings: Dict, tools: Optional[List[OrkesToolSchema]] = None) -> Dict:
        """
        Prepares the full payload for a request to the Google Gemini API.
        """
        message_payload = self.get_messages_payload(messages)

        if "max_tokens" in settings:
            settings["max_output_tokens"] = settings.pop("max_tokens")

        payload = {
            "generation_config": settings,
            **message_payload
        }

        if tools:
            payload['tools'] = self.get_tools_payload(tools)

        return payload

    def parse_response(self, response_data: Dict) -> RequestSchema:
        """
        Parses a response from the Google Gemini API.
        """
        try:
            candidate = response_data['candidates'][0]
            parts = candidate.get('content', {}).get('parts', [])
            
            tools_called = []
            text_content = ""

            for part in parts:
                if 'functionCall' in part:
                    fc = part['functionCall']
                    tool_schema = ToolCallSchema(
                        function_name=fc['name'],
                        arguments=fc.get('args', {})
                    )
                    tools_called.append(tool_schema)
                
                elif 'text' in part:
                    text_content += part['text']

            if tools_called:
                return RequestSchema(content_type="tool_calls", content=tools_called)
            
            return RequestSchema(content_type="message", content=text_content)

        except (KeyError, IndexError):
            raise ValueError(f"Unexpected Gemini response format: {response_data}")

    def parse_stream_chunk(self, line: str) -> Optional[str]:
        """
        Parses a single chunk of a streaming response from the Google Gemini API.
        """
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
