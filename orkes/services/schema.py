from typing import Optional, Dict, AsyncGenerator, Any, List, Union
from abc import ABC, abstractmethod
from requests import Response
from pydantic import BaseModel
from orkes.shared.schema import OrkesMessagesSchema, OrkesToolSchema, RequestSchema


class LLMProviderStrategy(ABC):
    """Abstract base class for LLM provider strategies.

    This class defines the interface for handling provider-specific logic, such as
    preparing payloads, parsing responses, and generating headers. Each provider
    (e.g., OpenAI, Anthropic) should have its own implementation of this class.
    """

    @abstractmethod

    def prepare_payload(self, model: str, messages: OrkesMessagesSchema, stream: bool, settings: Dict, tools: Optional[List[Dict]] = None) -> Dict:
        """Prepares the payload for a request to the LLM provider.

        Args:
            model (str): The name of the model to use.
            messages (OrkesMessagesSchema): The messages to send to the LLM.
            stream (bool): Whether to stream the response.
            settings (Dict): A dictionary of settings for the request.
            tools (Optional[List[Dict]], optional): A list of tools to provide to the
                LLM. Defaults to None.

        Returns:
            Dict: The prepared payload.
        """
        pass

    @abstractmethod

    def parse_response(self, response_data: Dict) -> RequestSchema:
        """Parses a response from the LLM provider.

        Args:
            response_data (Dict): The response data from the provider.

        Returns:
            RequestSchema: The parsed response.
        """
        pass

    @abstractmethod

    def parse_stream_chunk(self, chunk: str) -> Optional[str]:
        """Parses a single chunk of a streaming response.

        Args:
            chunk (str): A chunk of the response.

        Returns:
            Optional[str]: The parsed content of the chunk, or None if the chunk is
                           empty or a stop token.
        """
        pass

    @abstractmethod

    def get_headers(self, api_key: str) -> Dict[str, str]:
        """Gets the authentication headers for the LLM provider.

        Args:
            api_key (str): The API key for the provider.

        Returns:
            Dict[str, str]: A dictionary of headers.
        """
        pass

    @abstractmethod

    def get_messages_payload(self, messages: OrkesMessagesSchema) -> List[Dict]:
        """Converts an Orkes message schema to a format suitable for the LLM provider.

        Args:
            messages (OrkesMessagesSchema): The messages to convert.

        Returns:
            List[Dict]: The messages in the provider's format.
        """
        pass

    @abstractmethod

    def get_tools_payload(self, tools: List[OrkesToolSchema]) -> List[Dict]:
        """Converts an Orkes tool schema to a format suitable for the LLM provider.

        Args:
            tools (List[OrkesToolSchema]): The tools to convert.

        Returns:
            List[Dict]: The tools in the provider's format.
        """
        pass


class LLMInterface(ABC):
    """Abstract base class for LLM connections.

    This class defines the interface for sending and streaming messages to an LLM,
    as well as for performing health checks.
    """

    @abstractmethod
    def send_message(self, message, **kwargs) -> Response:
        """Sends a message to the LLM and receives the full response.

        Args:
            message: The message to send.
            **kwargs: Additional keyword arguments.

        Returns:
            Response: The response from the LLM.
        """
        pass

    @abstractmethod
    async def stream_message(self, message, **kwargs) -> AsyncGenerator[str, None]:
        """Streams the response from the LLM incrementally.

        Args:
            message: The message to send.
            **kwargs: Additional keyword arguments.

        Yields:
            str: A chunk of the response.
        """
        pass

    @abstractmethod
    def health_check(self) -> Response:
        """Checks the health status of the LLM server.

        Returns:
            Response: The response from the health check.
        """
        pass
