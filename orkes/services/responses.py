import json
from abc import ABC, abstractmethod
from typing import Type
from requests.models import Response


class ResponseInterface(ABC):
    """An abstract base class for handling LLM responses.

    This interface defines the methods for parsing both streaming and full
    responses from an LLM.
    """
    @abstractmethod
    def parse_stream_response(self, chunk: bytes, **kwargs) -> str:
        """Parses a single chunk of a streaming response from the LLM.

        Args:
            chunk (bytes): A chunk of the response.
            **kwargs: Additional keyword arguments.

        Returns:
            str: The parsed content of the chunk.
        """
        pass

    @abstractmethod
    def parse_full_response(self, payload: dict) -> dict:
        """Parses a full, non-streaming response from the LLM.

        Args:
            payload (dict): The full response payload.

        Returns:
            dict: The parsed response.
        """
        pass

    @abstractmethod
    def _generate_event(self, buffer: list) -> str:
        """Generates a Server-Sent Event (SSE) from the given data.

        Args:
            buffer (list): A list of strings to be included in the event.

        Returns:
            str: A formatted SSE string.
        """
        pass

class ChatResponse(ResponseInterface):
    """A response handler for chat-based LLM responses.

    This class is designed for streaming responses using Server-Sent Events (SSE).

    Attributes:
        eot_token (str): The end-of-transmission token to signal the end of a stream.
    """
    def __init__(self, end_token: str = "<|eot_id|>"):
        """Initializes the ChatResponse handler.

        Args:
            end_token (str, optional): The end-of-transmission token. Defaults to
                                     "<|eot_id|>".
        """
        self.eot_token = end_token

    def parse_stream_response(self, chunk: bytes, sse: bool = False) -> str:
        """Parses a single chunk of a streaming response.

        Args:
            chunk (bytes): A chunk of the response.
            sse (bool, optional): Whether to format the output as an SSE event.
                                Defaults to False.

        Returns:
            str: The parsed content of the chunk, optionally formatted as an SSE
                 event.
        """
        if not chunk:
            return ""

        chunk_str = chunk.decode('utf-8').strip()
        if not chunk_str or not chunk_str.startswith("data:"):
            return ""

        data_str = chunk_str[len("data:"):].strip()
        if data_str == "[DONE]":
            return "[DONE]"

        try:
            chunk_data = json.loads(data_str)
            delta_content = chunk_data['choices'][0]['delta'].get('content', '')
            v = "" if delta_content == self.eot_token else delta_content

        except json.JSONDecodeError:
            v = ""

        if sse:
            return self._generate_event([v])
        else:
            return v

    def _generate_event(self, buffer: list) -> str:
        """Generates an SSE event from a buffer of content."""
        event = {"v": "".join(buffer)}
        return f"event: delta\ndata: {json.dumps(event)}\n\n"

    def parse_full_response(self, payload: dict) -> dict:
        """Parses a full, non-streaming response.

        Note:
            This method is a placeholder and currently returns the payload as is.
        """
        return payload


class StreamResponseBuffer:
    """A buffer for handling streaming responses from an LLM.

    This class accumulates chunks of a streaming response and yields them as
    complete events, either when the buffer is full or when the stream ends.

    Attributes:
        headers: The headers of the response.
        llm_response (Type[ResponseInterface]): The response handler to use for
                                               parsing the stream.
        eot_token (str): The end-of-transmission token.
    """
    def __init__(self, llm_response: Type[ResponseInterface], headers=None, eot_token: str = "<EOT_TOKEN>"):
        """Initializes the StreamResponseBuffer.

        Args:
            llm_response (Type[ResponseInterface]): The response handler.
            headers (optional): The response headers. Defaults to None.
            eot_token (str, optional): The end-of-transmission token. Defaults to
                                     "<EOT_TOKEN>".
        """
        self.headers = headers
        self.llm_response = llm_response
        self.eot_token = eot_token

    async def stream(self, response: Response, buffer_size: int = 10, trigger_connection=None):
        """Streams the response, buffering and yielding events.

        Args:
            response (Response): The response object to stream.
            buffer_size (int, optional): The size of the buffer. Defaults to 10.
            trigger_connection (optional): A connection object to check for
                                         disconnections. Defaults to None.

        Yields:
            str: An SSE event string.
        """
        buffer = []

        if response.status_code == 200:
            for chunk in response.iter_lines():
                if trigger_connection:
                    if await trigger_connection.is_disconnected():
                        response.close()
                        break

                delta_content = self.llm_response.parse_stream_response(chunk)

                if delta_content == self.eot_token:
                    break

                if buffer_size > 0:
                    buffer.append(delta_content)

                if self._is_buffer_full(buffer, buffer_size):
                    yield self.llm_response._generate_event(buffer)
                    buffer.clear()

            if buffer:
                yield self.llm_response._generate_event(buffer)

        else:
            print(f"Error: {response.status_code}, {response.text}")

    def _is_buffer_full(self, buffer: list, buffer_size: int) -> bool:
        """Checks if the buffer has reached the specified size."""
        return len(buffer) >= buffer_size
