from abc import ABC, abstractmethod
from typing import Union, Dict
from orkes.services.schema import LLMInterface
import uuid

class AgentInterface(ABC):
    @abstractmethod
    async def ainvoke(self, queries: Union[str, Dict]):
        """Async Invoke the agent with a message."""
        pass

    @abstractmethod
    def invoke(self, queries: Union[str, Dict]):
        """Invoke the agent with a message."""
        pass

class Agent(AgentInterface):
    def __init__(self, name: str, llm_interface: LLMInterface):
        self.name = name
        self.id = self._create_id()
        self.llm_interface = llm_interface

    def _create_id(self):
        return "agent_"+str(uuid.uuid4())
