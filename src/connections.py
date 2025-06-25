from abc import ABC, abstractmethod
from typing import Optional, Dict
import requests
from requests import Response
import json

class LLMInterface(ABC):
    """
    Abstract base class for LLM connections.
    Defines methods to send, stream, and parse messages.
    """

    @abstractmethod
    def send_message(self) -> Response:
        """Send a message and receive the full response."""
        pass
    
    @abstractmethod
    def stream_message(self) -> Response:
        """Stream the response incrementally."""
        pass

    @abstractmethod
    def health_check(self) -> Response:
        """Check the server's health status."""
        pass



class vLLMConnection(LLMInterface):
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url = url
        self.headers = headers if headers else {
            'Content-Type': 'application/json',
        }

        self.default_setting = {
            "temperature": 0.2,
            "top_p": 0.6,
            "frequency_penalty": 0.2,
            "presence_penalty": 0,
            "seed": 22
        }

    def stream_message(self, message, model_name, end_point = "/v1/chat/completions", settings = None):
        full_url = self.url + end_point
        payload = {
            "messages": message,
            "model": model_name,
            "stream": True,
            **(settings if settings else self.default_settings)
        }
        # Post request to the full URL with the payload
        response = requests.post(full_url, headers=self.headers, data=json.dumps(payload), stream=True)
        return response

    def generate_message(self, message, model_name, end_point="/v1/chat/completions", settings=None):
        full_url = self.url + end_point
        payload = {
            "messages": message,
            "model": model_name,
            "stream": False,
            **(settings if settings else self.default_settings)
        }
        # Post request to the full URL with the payload
        response = requests.post(full_url, headers=self.headers, data=json.dumps(payload))
        return response


    def health_check(self, end_point="/health"):
        full_url = self.url + end_point
        return requests.get(full_url, headers=self.headers)

