from abc import ABC, abstractmethod
from typing import Optional, Dict
import requests
from requests import Response
import json

class LLMInterface(ABC):
    """
    Abstract base class for LLM connections.
    Defines methods to send, streams.
    """

    @abstractmethod
    def send_message(self, message, **kwargs) -> Response:
        """Send a message and receive the full response."""
        pass
    
    @abstractmethod
    def stream_message(self, message, **kwargs) -> Response:
        """Stream the response incrementally."""
        pass

    @abstractmethod
    def health_check(self) -> Response:
        """Check the server's health status."""
        pass



class vLLMConnection(LLMInterface):
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

    def stream_message(self, message, end_point = "/v1/chat/completions", settings = None):
        full_url = self.url + end_point
        payload = {
            "messages": message,
            "model": self.model_name,
            "stream": True,
            **(settings if settings else self.default_setting)
        }
        # Post request to the full URL with the payload
        response = requests.post(full_url, headers=self.headers, data=json.dumps(payload), stream=True)
        return response

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

