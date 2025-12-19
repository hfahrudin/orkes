from typing import Optional, Dict, AsyncGenerator, Any, List, Union
from abc import ABC, abstractmethod
from requests import Response
from pydantic import BaseModel

class ToolCallSchema(BaseModel):
    """Schema for tool call information in LLM responses."""
    function_name: str
    arguments: Dict[str, Any]

class ResponseSchema(BaseModel):
    """Schema for a standard LLM response."""
    content_type: str
    content : Union[str, List[ToolCallSchema]]

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
    def parse_response(self, response_data: Dict) -> ResponseSchema:
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
    def stream_message(self, message, **kwargs) -> AsyncGenerator[str, None]:
        """Stream the response incrementally."""
        pass

    @abstractmethod
    def health_check(self) -> Response:
        """Check the server's health status."""
        pass
