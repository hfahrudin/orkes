
from typing import Any, Callable, Dict
import uuid
from abc import ABC, abstractmethod
from orkes.graph.schema import NodePoolItem

class Node:
    def __init__(self, name: str, func: Callable, graph_state):
        """
        Initialize a Node.

        Parameters:
        - name (str): The unique identifier for the node.
        - name (func): The unique identifier for the node.
        """
        self.name: str = name
        self.func: Callable = func
        self.graph_state = graph_state
        self.id = "node_"+str(uuid.uuid4())
        self.description = func.__doc__

    def execute(self, input_state) -> Any:
        output = self.func(input_state)
        return output

    def __repr__(self) -> str:
        return f"Node({self.name})"


#TODO: add START NODE INVOKE initialitation
class _StartNode(Node):
    """Special START node — entry point of the graph."""
    def __init__(self, graph_state):
        super().__init__("START", self._start, graph_state)

    def _start(self, state):
        # START usually just forwards state
        return state
        

class _EndNode(Node):
    """Special END node — termination point of the graph."""
    def __init__(self, graph_state):
        super().__init__("END", self._end, graph_state)

    def _end(self, state):
        # END could finalize/clean state before returning
        return state

class Edge(ABC):
    def __init__(self, from_node: NodePoolItem, to_node: NodePoolItem = None, max_passes=25):
        self.id = "edge_"+str(uuid.uuid4())
        self.from_node = from_node
        self.to_node = to_node
        self.passes = 0
        self.max_passes = max_passes
        self.edge_type = None

    # @abstractmethod
    # def should_transfer(self, data: Any) -> bool:
    #     """Must be implemented by all edge types."""
    #     pass

    def __repr__(self):
        return f"{self.__class__.__name__}({self.id})"

class ForwardEdge(Edge):
    def __init__(self, from_node: NodePoolItem, to_node: NodePoolItem, max_passes: int = 25):
        super().__init__(from_node, to_node, max_passes)
        self.edge_type = "__forward__"

class ConditionalEdge(Edge):
    def __init__(
        self,
        from_node: NodePoolItem,
        gate_function: Callable,
        condition: Dict[str, str],
        max_passes=25
    ):
        super().__init__(from_node, to_node=None, max_passes=max_passes)  # initialize parent part
        self.gate_function = gate_function
        self.condition = condition
        self.edge_type = "__conditional__"

    # def should_transfer(self, data: Any) -> bool:
    #     self.passes += 1
    #     return self.condition(data) and self.passes <= self.max_passes

NodePoolItem.model_rebuild()  


#Runner constarain for now: support fallback, condtional, :
# find Start Node:
# node_pool is the mapper: { Node:node, "edge" : edge}
