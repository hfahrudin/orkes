from typing import Optional, Dict, AsyncGenerator, Any, Callable
import requests
import aiohttp
from orkes.services.strategies import LLMProviderStrategy, OpenAIStyleStrategy, AnthropicStrategy, GoogleGeminiStrategy
from orkes.services.schema import LLMInterface, OrkesToolSchema
from orkes.shared.schema import OrkesMessagesSchema
from orkes.shared.context import edge_trace_var
from orkes.graph.schema import LLMTraceSchema
from orkes.shared.utils import callable_to_orkes_tool_schema

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

    def send_message(self, messages: OrkesMessagesSchema, endpoint: str = None, tools: Optional[list[OrkesToolSchema | Callable]] = None, connection: Optional[Any] = None, **kwargs) -> Dict:
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
        
        processed_tools = []
        if tools:
            for tool in tools:
                if callable(tool):
                    processed_tools.append(callable_to_orkes_tool_schema(tool))
                else:
                    processed_tools.append(tool)

        payload = self.provider.prepare_payload(
            self.config.model,
            messages,
            stream=False,
            settings=settings,
            tools=processed_tools if len(processed_tools) > 0 else None
        )

        edge_trace = edge_trace_var.get()

        response = requests.post(full_url, headers=self.session_headers, json=payload)
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

    async def stream_message(self, messages: OrkesMessagesSchema, endpoint: str = None, tools: Optional[list[OrkesToolSchema | Callable]] = None, connection: Optional[Any] = None, **kwargs) -> AsyncGenerator[str, None]:
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

        processed_tools = []
        if tools:
            for tool in tools:
                if callable(tool):
                    processed_tools.append(callable_to_orkes_tool_schema(tool))
                else:
                    processed_tools.append(tool)

        payload = self.provider.prepare_payload(
            self.config.model,
            messages,
            stream=True,
            settings=self._merge_settings(kwargs),
            tools=processed_tools if len(processed_tools) > 0 else None
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(full_url, headers=self.session_headers, json=payload) as response:
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
        except requests.RequestException:
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
