
from typing import Any, Dict, Callable
import uuid
from abc import ABC, abstractmethod

class Node:
    def __init__(self, name: str, func: Callable):
        """
        Initialize a Node.

        Parameters:
        - name (str): The unique identifier for the node.
        - name (func): The unique identifier for the node.
        """
        self.name: str = name
        self.func: Callable = func

    def execute(self, state) -> Any:
        output = self.func(state)
        return output

    def __repr__(self) -> str:
        return f"Node({self.name})"

class _StartNode(Node):
    """Special START node — entry point of the graph."""
    def __init__(self):
        super().__init__("START", self._start)

    def _start(self, state):
        # START usually just forwards state
        return state
        

class _EndNode(Node):
    """Special END node — termination point of the graph."""
    def __init__(self):
        super().__init__("END", self._end)

    def _end(self, state):
        # END could finalize/clean state before returning
        return state

class Edge(ABC):
    def __init__(self, from_node: Node, to_node: Node = None, max_passes=5):
        self.id = str(uuid.uuid4())
        self.from_node = from_node
        self.to_node = to_node
        self.passes = 0
        self.max_passes = max_passes

    @abstractmethod
    def should_transfer(self, data: Any) -> bool:
        """Must be implemented by all edge types."""
        pass

    def __repr__(self):
        return f"{self.__class__.__name__}({self.id})"

class ForwardEdge(Edge):
    def should_transfer(self, data: Any) -> bool:
        self.passes += 1
        return self.passes <= self.max_passes

class ConditionalEdge(Edge):
    def __init__(self, from_node: str, judge_func: Callable, condition: Callable, max_passes=5):
        super().__init__(from_node, None, max_passes)
        self.judge_func = judge_func
        self.condition = condition

    def should_transfer(self, data: Any) -> bool:
        self.passes += 1
        return self.condition(data) and self.passes <= self.max_passes





#Runner constarain for now: support fallback, condtional, :
# find Start Node:
# node_pool is the mapper: { Node:node, "edge" : edge}