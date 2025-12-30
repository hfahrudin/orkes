from typing import Optional, Dict, AsyncGenerator, Any, List
import requests
import json
import aiohttp
import asyncio
from orkes.services.strategies import LLMProviderStrategy, OpenAIStyleStrategy, AnthropicStrategy, GoogleGeminiStrategy
from orkes.services.schema import LLMInterface
from orkes.shared.schema import OrkesMessagesSchema
from orkes.shared.context import edge_trace_var
from orkes.graph.schema import LLMTraceSchema

class LLMConfig:
    """A universal configuration object for any LLM connection.

    This class holds the necessary configuration parameters to connect to an LLM provider,
    such as API keys, base URLs, and model names. It also allows for custom headers and
    default parameters to be set for all requests.

    Attributes:
        api_key (str): The API key for the LLM provider.
        base_url (str): The base URL of the LLM provider's API.
        model (str): The name of the model to use.
        headers (Dict[str, str]): A dictionary of extra headers to send with each request.
        default_params (Dict[str, Any]): A dictionary of default parameters to use for
                                       all requests, such as temperature and max_tokens.
    """
    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str,
        extra_headers: Optional[Dict[str, str]] = None,
        default_params: Optional[Dict[str, Any]] = None
    ):
        """Initializes the LLMConfig object.

        Args:
            api_key (str): The API key for the LLM provider.
            base_url (str): The base URL of the LLM provider's API.
            model (str): The name of the model to use.
            extra_headers (Optional[Dict[str, str]], optional): A dictionary of extra
                headers to send with each request. Defaults to None.
            default_params (Optional[Dict[str, Any]], optional): A dictionary of default
                parameters to use for all requests. Defaults to a standard set of
                parameters.
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.headers = extra_headers or {}
        self.default_params = default_params or {
            "temperature": 0.7,
            "max_tokens": 1024
        }


class vLLMConnection(LLMInterface):
    """LEGACY: This class is maintained for backward compatibility only.

    .. deprecated:: 0.1.0
       Use :class:`LLMFactory` for prebuilt connections or create your own connection
       using :class:`UniversalLLMClient`. `vLLMConnection` uses the OpenAI-compatible
       format which is being phased out.
    """
    def __init__(self, url: str, model_name=str, headers: Optional[Dict[str, str]] = None, api_key=None):
        self.url = url
        self.headers = headers.copy() if headers else {"Content-Type": "application/json"}
        if api_key:
            self.headers["Authorization"] = f"Bearer {api_key}"

        self.default_setting = {
            "temperature": 0.2,
            "top_p": 0.6,
            "frequency_penalty": 0.2,
            "presence_penalty": 0,
            "seed": 22
        }
        self.model_name = model_name

    async def stream_message(self, message, end_point="/v1/chat/completions", settings=None) -> AsyncGenerator[str, None]:
        full_url = self.url + end_point
        payload = {
            "messages": message,
            "model": self.model_name,
            "stream": True,
            **(settings if settings else self.default_setting)
        }
        # Post request to the full URL with the payload
        response = requests.post(full_url, headers=self.headers, data=json.dumps(payload), stream=True)
        for line in response.iter_lines():
            yield line

    def send_message(self, message, end_point="/v1/chat/completions", settings=None):
        full_url = self.url + end_point
        payload = {
            "messages": message,
            "model": self.model_name,
            "stream": False,
            **(settings if settings else self.default_setting)
        }
        # Post request to the full URL with the payload
        response = requests.post(full_url, headers=self.headers, data=json.dumps(payload))
        return response

    def health_check(self, end_point="/health"):
        full_url = self.url + end_point
        return requests.get(full_url, headers=self.headers)


class UniversalLLMClient(LLMInterface):
    """A universal client for interacting with various LLM providers.

    This client uses a strategy pattern to support different LLM providers, allowing
    for a consistent interface regardless of the underlying provider. It handles both
    synchronous and asynchronous requests, as well as streaming responses.

    Attributes:
        config (LLMConfig): The configuration for the LLM connection.
        provider (LLMProviderStrategy): The strategy for the specific LLM provider.
        session_headers (Dict[str, str]): The headers to use for the session.
    """
    def __init__(self, config: LLMConfig, provider: LLMProviderStrategy):
        """Initializes the UniversalLLMClient.

        Args:
            config (LLMConfig): The configuration for the LLM connection.
            provider (LLMProviderStrategy): The strategy for the specific LLM provider.
        """
        self.config = config
        self.provider = provider
        self.session_headers = self.provider.get_headers(self.config.api_key)
        self.session_headers.update(self.config.headers)

    def _merge_settings(self, overrides: Optional[Dict]) -> Dict:
        """Merges default settings with any overrides."""
        settings = self.config.default_params.copy()
        if overrides:
            settings.update(overrides)
        return settings

    def send_message(self, messages: OrkesMessagesSchema, endpoint: str = None, tools: Optional[List[Dict]] = None, connection: Optional[Any] = None, **kwargs) -> Dict:
        """Sends a synchronous request to the LLM provider.

        Args:
            messages (OrkesMessagesSchema): The messages to send to the LLM.
            endpoint (str, optional): The API endpoint to use. If not provided, it will
                be inferred from the provider.
            tools (Optional[List[Dict]], optional): A list of tools to provide to the
                LLM. Defaults to None.
            connection (Optional[Any], optional): The connection object from a web server,
                which can be used to check for client disconnection. Defaults to None.
            **kwargs: Additional parameters to override the default settings.

        Returns:
            Dict: A dictionary containing the raw response from the provider and the
                  parsed content.

        Raises:
            requests.RequestException: If the request fails.
        """
        if endpoint is None:
            if isinstance(self.provider, GoogleGeminiStrategy):
                endpoint = f"/models/{self.config.model}:generateContent"
            elif isinstance(self.provider, AnthropicStrategy):
                endpoint = "/messages"
            else:
                endpoint = "/chat/completions"

        full_url = f"{self.config.base_url}{endpoint}"

        settings = self._merge_settings(kwargs)
        payload = self.provider.prepare_payload(
            self.config.model,
            messages,
            stream=False,
            settings=settings,
            tools=tools
        )

        params = {}
        edge_trace = edge_trace_var.get()

        try:
            response = requests.post(full_url, headers=self.session_headers, json=payload, params=params)
            response.raise_for_status()
            data = response.json()
            parsed_response = self.provider.parse_response(data)

            if edge_trace:
                llm_trace = LLMTraceSchema(
                    messages=messages,
                    tools=tools,
                    parsed_response=parsed_response,
                    model=self.config.model,
                    settings=settings
                )
                edge_trace.llm_traces.append(llm_trace)

            return {
                "raw": data,
                "content": parsed_response.model_dump()
            }
        except requests.RequestException as e:
            raise

    async def stream_message(self, messages: OrkesMessagesSchema, endpoint: str = None, tools: Optional[List[Dict]] = None, connection: Optional[Any] = None, **kwargs) -> AsyncGenerator[str, None]:
        """Sends an asynchronous request to the LLM provider and streams the response.

        Args:
            messages (OrkesMessagesSchema): The messages to send to the LLM.
            endpoint (str, optional): The API endpoint to use. If not provided, it will
                be inferred from the provider.
            tools (Optional[List[Dict]], optional): A list of tools to provide to the
                LLM. Defaults to None.
            connection (Optional[Any], optional): The connection object from a web server,
                which can be used to check for client disconnection. Defaults to None.
            **kwargs: Additional parameters to override the default settings.

        Yields:
            str: A chunk of the response from the LLM.

        Raises:
            aiohttp.ClientError: If the request fails.
        """
        if endpoint is None:
            if isinstance(self.provider, GoogleGeminiStrategy):
                endpoint = f"/models/{self.config.model}:streamGenerateContent?alt=sse"
            elif isinstance(self.provider, AnthropicStrategy):
                endpoint = "/messages"
            else:
                endpoint = "/chat/completions"

        full_url = f"{self.config.base_url}{endpoint}"

        payload = self.provider.prepare_payload(
            self.config.model,
            messages,
            stream=True,
            settings=self._merge_settings(kwargs),
            tools=tools
        )

        params = {}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(full_url, headers=self.session_headers, json=payload, params=params) as response:
                    response.raise_for_status()
                    async for line in response.content:
                        if connection and hasattr(connection, 'is_disconnected'):
                            if await connection.is_disconnected():
                                break

                        decoded_line = line.decode('utf-8').strip()
                        if not decoded_line:
                            continue
                        text_chunk = self.provider.parse_stream_chunk(decoded_line)
                        if text_chunk:
                            yield text_chunk
        except (aiohttp.ClientError, asyncio.CancelledError) as e:
            raise

    def health_check(self, endpoint: str = "/health") -> bool:
        """Performs a health check on the LLM provider.

        Args:
            endpoint (str, optional): The health check endpoint. Defaults to "/health".

        Returns:
            bool: True if the provider is healthy, False otherwise.
        """
        try:
            full_url = f"{self.config.base_url}{endpoint}"
            response = requests.get(full_url, headers=self.session_headers)
            return response.status_code == 200
        except:
            return False


class LLMFactory:
    """A factory for creating pre-configured :class:`UniversalLLMClient` instances.

    This factory provides static methods to create clients for various LLM
    providers, such as vLLM, OpenAI, Anthropic, and Google Gemini.
    """
    @staticmethod
    def create_vllm(url: str, model: str, api_key: str = "EMPTY", base_url: str = None) -> UniversalLLMClient:
        """Creates a client for a vLLM-compatible server.

        Args:
            url (str): The URL of the vLLM server.
            model (str): The name of the model to use.
            api_key (str, optional): The API key to use. Defaults to "EMPTY".
            base_url (str, optional): The base URL of the API. If not provided, it will
                be inferred from the `url`.

        Returns:
            UniversalLLMClient: A client configured for the vLLM server.
        """
        config = LLMConfig(
            api_key=api_key,
            base_url=base_url or url,
            model=model
        )
        return UniversalLLMClient(config, OpenAIStyleStrategy())

    @staticmethod
    def create_openai(api_key: str, model: str = "gpt-4", base_url: str = "https://api.openai.com/v1") -> UniversalLLMClient:
        """Creates a client for the OpenAI API.

        Args:
            api_key (str): The OpenAI API key.
            model (str, optional): The name of the model to use. Defaults to "gpt-4".
            base_url (str, optional): The base URL of the OpenAI API. Defaults to
                "https://api.openai.com/v1".

        Returns:
            UniversalLLMClient: A client configured for the OpenAI API.
        """
        config = LLMConfig(
            api_key=api_key,
            base_url=base_url,
            model=model
        )
        return UniversalLLMClient(config, OpenAIStyleStrategy())

    @staticmethod
    def create_anthropic(api_key: str, model: str = "claude-3-opus-20240229", base_url: str = "https://api.anthropic.com/v1") -> UniversalLLMClient:
        """Creates a client for the Anthropic API.

        Args:
            api_key (str): The Anthropic API key.
            model (str, optional): The name of the model to use. Defaults to
                "claude-3-opus-20240229".
            base_url (str, optional): The base URL of the Anthropic API. Defaults to
                "https://api.anthropic.com/v1".

        Returns:
            UniversalLLMClient: A client configured for the Anthropic API.
        """
        config = LLMConfig(
            api_key=api_key,
            base_url=base_url,
            model=model
        )
        return UniversalLLMClient(config, AnthropicStrategy())

    @staticmethod
    def create_gemini(api_key: str, model: str = "gemini-2.0-flash", base_url: str = "https://generativelanguage.googleapis.com/v1beta") -> UniversalLLMClient:
        """Creates a client for the Google Gemini API.

        Args:
            api_key (str): The Google Gemini API key.
            model (str, optional): The name of the model to use. Defaults to
                "gemini-2.0-flash".
            base_url (str, optional): The base URL of the Google Gemini API. Defaults to
                "https://generativelanguage.googleapis.com/v1beta".

        Returns:
            UniversalLLMClient: A client configured for the Google Gemini API.
        """
        config = LLMConfig(
            api_key=api_key,
            base_url=base_url,
            model=model
        )
        return UniversalLLMClient(config, GoogleGeminiStrategy())
    


# NOTE: Example usage 

# async def main():
#     # 1. Setup for vLLM (Self-hosted)
#     vllm_client = LLMFactory.create_vllm(
#         url="http://localhost:8000/v1", 
#         model="meta-llama/Llama-2-7b-chat-hf"
#     )

#     # 2. Setup for OpenAI
#     openai_client = LLMFactory.create_openai(
#         api_key="sk-...", 
#         model="gpt-4o"
#     )

#     messages = [{"role": "user", "content": "Explain quantum physics in 10 words."}]

#     print("--- vLLM Sync Response ---")
#     try:
#         response = vllm_client.send_message(messages)
#         print(response['content'])
#     except Exception as e:
#         print(f"vLLM connection failed (expected if no server running): {e}")

#     print("\n--- OpenAI Stream Response ---")
#     # This assumes you have a valid key, otherwise it will error gracefully
#     try:
#         async for chunk in openai_client.stream_message(messages):
#             print(chunk, end="", flush=True)
#     except Exception as e:
#         print(f"OpenAI connection failed: {e}")

# if __name__ == "__main__":
#     asyncio.run(main())

# Building Your Own Connector

# To connect to a new LLM provider, you can create your own connector by
# implementing the `LLMProviderStrategy` and using it with the
# `UniversalLLMClient`. This allows you to define the specific logic for
# preparing payloads, parsing responses, and handling authentication for any
# provider.

# The following example demonstrates how to create a custom strategy for a
# fictional "MyLLM" provider and use it to make API calls.

# ```python
# from orkes.services.strategies import LLMProviderStrategy
# from orkes.services.schema import RequestSchema, ToolCallSchema
# from orkes.shared.schema import OrkesMessagesSchema, OrkesToolSchema
# from typing import Dict, List, Optional
# import json

# class MyLLMStrategy(LLMProviderStrategy):
#     """
#     A custom strategy for the fictional MyLLM provider.
#     """
#     def get_headers(self, api_key: str) -> Dict[str, str]:
#         """
#         Returns the authentication headers for MyLLM.
#         """
#         return {
#             "Authorization": f"Bearer {api_key}",
#             "Content-Type": "application/json"
#         }

#     def get_messages_payload(self, messages: OrkesMessagesSchema) -> Dict[str, List[Dict]]:
#         """
#         Converts an OrkesMessagesSchema into the format expected by MyLLM.
#         """
        
#         processed_messages = [msg.model_dump() for msg in messages.messages]
#         return {"chat_messages": processed_messages}

#     def get_tools_payload(self, tools: List[OrkesToolSchema]) -> List[Dict]:
#         """
#         Converts a list of OrkesToolSchema objects into the format expected by MyLLM.
#         """
#         return [{"tool_info": tool.model_dump()} for tool in tools]

#     def prepare_payload(self, model: str, messages: OrkesMessagesSchema, stream: bool, settings: Dict, tools: Optional[List[OrkesToolSchema]] = None) -> Dict:
#         """
#         Prepares the full payload for a request to MyLLM.
#         """
#         payload = {
#             "model_name": model,
#             "streaming": stream,
#             "configurations": settings,
#             **self.get_messages_payload(messages)
#         }
#         if tools:
#             payload['available_tools'] = self.get_tools_payload(tools)
#         return payload

#     def parse_response(self, response_data: Dict) -> RequestSchema:
#         """
#         Parses a response from MyLLM.
#         """
#         if 'tool_invocations' in response_data:
#             tools_called = [
#                 ToolCallSchema(function_name=tool['name'], arguments=tool['args'])
#                 for tool in response_data['tool_invocations']
#             ]
#             return RequestSchema(content_type="tool_calls", content=tools_called)
#         return RequestSchema(content_type="message", content=response_data['text_response'])

#     def parse_stream_chunk(self, line: str) -> Optional[str]:
#         """
#         Parses a single chunk of a streaming response from MyLLM.
#         """
#         if line.startswith("chunk: "):
#             return line[7:]
#         return None

# # --- Example Usage ---
# # 1. Create a configuration for your custom LLM.
# myllm_config = LLMConfig(
#     api_key="my-secret-api-key",
#     base_url="https://api.myllm.com/v1",
#     model="my-awesome-model-v1"
# )

# # 2. Instantiate the UniversalLLMClient with your custom strategy.
# myllm_client = UniversalLLMClient(myllm_config, MyLLMStrategy())

# # 3. Use the client to send messages.
# try:
#     response = myllm_client.send_message(
#         messages=OrkesMessagesSchema(messages=[{"role": "user", "content": "Hello, MyLLM!"}])
#     )
#     print(response['content'])
# except Exception as e:
#     print(f"MyLLM connection failed: {e}")
# ```
