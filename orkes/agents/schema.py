from abc import ABC, abstractmethod
from typing import Union, Dict, Any, AsyncIterator, Iterator
from orkes.services.schema import LLMInterface
import uuid

class AgentInterface(ABC):
    """Abstract base class for all agents.

    This interface defines the common methods that all agents should implement.
    Agents are responsible for processing input queries and returning results,
    either synchronously or asynchronously, as a single response or a stream.
    """

    @abstractmethod
    def invoke(self, queries: Union[str, Dict[str, Any]]) -> Any:
        """Invoke the agent with a message.

        Args:
            queries (Union[str, Dict[str, Any]]): The input to the agent.

        Returns:
            Any: The agent's response.
        """
        pass

    @abstractmethod
    async def ainvoke(self, queries: Union[str, Dict[str, Any]]) -> Any:
        """Asynchronously invoke the agent with a message.

        Args:
            queries (Union[str, Dict[str, Any]]): The input to the agent.

        Returns:
            Any: The agent's response.
        """
        pass

    @abstractmethod
    def stream(self, queries: Union[str, Dict[str, Any]]) -> Iterator[Any]:
        """Stream the agent's response synchronously.

        Args:
            queries (Union[str, Dict[str, Any]]): The input to the agent.

        Returns:
            Iterator[Any]: An iterator of the agent's response.
        """
        pass

    @abstractmethod
    async def astream(self, queries: Union[str, Dict[str, Any]]) -> AsyncIterator[Any]:
        """Stream the agent's response asynchronously.

        Args:
            queries (Union[str, Dict[str, Any]]): The input to the agent.

        Returns:
            AsyncIterator[Any]: An async iterator of the agent's response.
        """
        pass

class Agent(AgentInterface):
    """Base class for agents.

    This class provides a default implementation of the `AgentInterface`.
    It is intended to be subclassed by specific agent implementations.

    Attributes:
        name (str): The name of the agent.
        llm_interface (LLMInterface): The LLM interface to use.
    """
    def __init__(self, name: str, llm: LLMInterface):
        """Initializes an Agent.

        Args:
            name (str): The name of the agent.
            llm (LLMInterface): The LLM interface to use.
        """
        self.name = name
        self.llm_interface = llm

    def invoke(self, queries: Union[str, Dict[str, Any]]) -> Any:
        raise NotImplementedError

    async def ainvoke(self, queries: Union[str, Dict[str, Any]]) -> Any:
        raise NotImplementedError

    def stream(self, queries: Union[str, Dict[str, Any]]) -> Iterator[Any]:
        raise NotImplementedError

    async def astream(self, queries: Union[str, Dict[str, Any]]) -> AsyncIterator[Any]:
        raise NotImplementedError
