from abc import ABC, abstractmethod
from typing import Union, Dict, Any, AsyncIterator, Iterator
from orkes.services.schema import LLMInterface
import uuid

class AgentInterface(ABC):
    @abstractmethod
    def invoke(self, queries: Union[str, Dict[str, Any]]) -> Any:
        """Invoke the agent with a message."""
        pass

    @abstractmethod
    async def ainvoke(self, queries: Union[str, Dict[str, Any]]) -> Any:
        """Async Invoke the agent with a message."""
        pass

    @abstractmethod
    def stream(self, queries: Union[str, Dict[str, Any]]) -> Iterator[Any]:
        """Stream the agent response synchronously."""
        pass

    @abstractmethod
    async def astream(self, queries: Union[str, Dict[str, Any]]) -> AsyncIterator[Any]:
        """Stream the agent response asynchronously."""
        pass
