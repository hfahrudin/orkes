from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Union, Dict


class AgentInterface(ABC):

    @abstractmethod
    async def ainvoke(self, queries: Union[str, Dict]):
        """Async Invoke the agent with a message."""
        pass

    @abstractmethod
    def invoke(self, queries: Union[str, Dict]):
        """Invoke the agent with a message."""
        pass
