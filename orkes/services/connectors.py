from typing import Optional, Dict, AsyncGenerator, Any, List
import requests
import json
import aiohttp
from orkes.services.strategies import LLMProviderStrategy, OpenAIStyleStrategy, AnthropicStrategy, GoogleGeminiStrategy
from orkes.services.schema import LLMInterface
from orkes.shared.schema import OrkesMessagesSchema

class LLMConfig:
    """Universal configuration object for any LLM connection."""
    def __init__(
        self, 
        api_key: str, 
        base_url: str, 
        model: str, 
        extra_headers: Optional[Dict[str, str]] = None,
        default_params: Optional[Dict[str, Any]] = None
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.headers = extra_headers or {}
        self.default_params = default_params or {
            "temperature": 0.7,
            "max_tokens": 1024
        }


class vLLMConnection(LLMInterface):
    """
    LEGACY: This class is maintained for backward compatibility only.
    
    .. 
       Use :class:`LLMFactory` for prebuilt connection or create your connection using `UniversalLLMClient`. 
       vLLMConnection uses the OpenAI-compatible format which is being phased out.
    """
    def __init__(self, url: str, model_name = str, headers: Optional[Dict[str, str]] = None, api_key = None):
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

    async def stream_message(self, message, end_point = "/v1/chat/completions", settings = None)  -> AsyncGenerator[str, None]:
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

#TODO: validate schema of responses of tools too
class UniversalLLMClient(LLMInterface):
    def __init__(self, config: LLMConfig, provider: LLMProviderStrategy):
        self.config = config
        self.provider = provider
        self.session_headers = self.provider.get_headers(self.config.api_key)
        self.session_headers.update(self.config.headers)

    def _merge_settings(self, overrides: Optional[Dict]) -> Dict:
        settings = self.config.default_params.copy()
        if overrides:
            settings.update(overrides)
        return settings

    def send_message(self, messages: OrkesMessagesSchema, endpoint: str = None, tools: Optional[List[Dict]] = None, **kwargs) -> Dict:
        """Synchronous Send"""
        if endpoint is None:
            if isinstance(self.provider, GoogleGeminiStrategy):
                endpoint = f"/models/{self.config.model}:generateContent"
            elif isinstance(self.provider, AnthropicStrategy):
                endpoint = "/messages"
            else:
                endpoint = "/chat/completions"

        full_url = f"{self.config.base_url}{endpoint}"

        payload = self.provider.prepare_payload(
            self.config.model, 
            messages, 
            stream=False, 
            settings=self._merge_settings(kwargs),
            tools=tools
        )

        # Special handling for Google which uses query params for API key sometimes
        params = {}
        # if isinstance(self.provider, GoogleGeminiStrategy):
        #     params['key'] = self.config.api_key

        try:
            response = requests.post(full_url, headers=self.session_headers, json=payload, params=params)
            response.raise_for_status()
            data = response.json()
            # Return raw data + parsed content for convenience
            return {
                "raw": data,
                "content": self.provider.parse_response(data).model_dump()
            }
        except requests.RequestException as e:
            # logging.error(f"Request failed: {e}")
            raise

    async def stream_message(self, messages: OrkesMessagesSchema, endpoint: str = None, tools: Optional[List[Dict]] = None, **kwargs) -> AsyncGenerator[str, None]:
        """Asynchronous Streaming"""
        if endpoint == None:
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

        async with aiohttp.ClientSession() as session:
            async with session.post(full_url, headers=self.session_headers, json=payload, params=params) as response:
                response.raise_for_status()
                async for line in response.content:
                    decoded_line = line.decode('utf-8').strip()
                    if not decoded_line:
                        continue
                    text_chunk = self.provider.parse_stream_chunk(decoded_line)
                    if text_chunk:
                        yield text_chunk

    def health_check(self, endpoint: str = "/health") -> bool:
        try:
            full_url = f"{self.config.base_url}{endpoint}"
            response = requests.get(full_url, headers=self.session_headers)
            return response.status_code == 200
        except:
            return False


class LLMFactory:
    @staticmethod
    def create_vllm(url: str, model: str, api_key: str = "EMPTY", base_url: str = None) -> UniversalLLMClient:
        config = LLMConfig(
            api_key=api_key,
            base_url=base_url or url,
            model=model
        )
        return UniversalLLMClient(config, OpenAIStyleStrategy())

    @staticmethod
    def create_openai(api_key: str, model: str = "gpt-4", base_url: str = "https://api.openai.com/v1") -> UniversalLLMClient:
        config = LLMConfig(
            api_key=api_key,
            base_url=base_url,
            model=model
        )
        return UniversalLLMClient(config, OpenAIStyleStrategy())

    @staticmethod
    def create_anthropic(api_key: str, model: str = "claude-3-opus-20240229", base_url: str = "https://api.anthropic.com/v1") -> UniversalLLMClient:
        config = LLMConfig(
            api_key=api_key,
            base_url=base_url,
            model=model
        )
        return UniversalLLMClient(config, AnthropicStrategy())
    
    @staticmethod
    def create_gemini(api_key: str, model: str = "gemini-2.0-flash", base_url: str = "https://generativelanguage.googleapis.com/v1beta") -> UniversalLLMClient:
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
