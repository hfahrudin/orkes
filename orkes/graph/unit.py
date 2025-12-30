
from typing import Any, Callable, Dict
import uuid
from abc import ABC, abstractmethod
from orkes.graph.schema import NodePoolItem, NodeTrace, EdgeTrace

class Node:
    """Represents a node in the computational graph.

    Each node encapsulates a function to be executed and maintains its state
    within the graph.

    Attributes:
        name (str): The unique identifier for the node.
        func (Callable): The function to be executed by this node.
        graph_state: A reference to the graph's state.
        id (str): A unique identifier for the node instance.
        description (str): The docstring of the function.
        node_trace (NodeTrace): The trace object for the node.
    """
    def __init__(self, name: str, func: Callable, graph_state):
        """Initializes a Node.

        Args:
            name (str): The unique identifier for the node.
            func (Callable): The function to be executed by this node. The function
                         should accept the graph's state as input and return an
                         output that contributes to the state.
            graph_state: A reference to the graph's state, allowing the node to
                         interact with and modify it.
        """
        self.name: str = name
        self.func: Callable = func
        self.graph_state = graph_state
        self.id = "node_" + str(uuid.uuid4())
        self.description = func.__doc__
        self.node_trace = NodeTrace(
            node_name=self.name,
            node_id=self.id,
            node_description=self.description,
            meta={
                "type": "function_node"
            }
        )

    def execute(self, input_state) -> Any:
        """Executes the node's function.

        Args:
            input_state: The input state for the function.

        Returns:
            Any: The output of the function.
        """
        output = self.func(input_state)
        return output

    def __repr__(self) -> str:
        return f"Node({self.name})"


class _StartNode(Node):
    """A special node that marks the entry point of the graph.

    It is the first node to be executed and typically forwards the initial state
    to the next nodes.
    """
    def __init__(self, graph_state):
        super().__init__("START", self._start, graph_state)
        self.node_trace.meta = {
            "type": "start_node"
        }
        self.node_trace.node_description = self.func.__doc__

    def _start(self, state):
        """The entry point of the graph."""
        return state


class _EndNode(Node):
    """A special node that marks the termination point of the graph.

    When the execution reaches this node, the graph's run is considered complete.
    It can be used for finalizing the state or cleaning up resources.
    """
    def __init__(self, graph_state):
        super().__init__("END", self._end, graph_state)
        self.node_trace.node_description = self.func.__doc__
        self.node_trace.meta = {
            "type": "end_node"
        }

    def _end(self, state):
        """The termination point of the graph."""
        return state

class Edge(ABC):
    """Represents a directed connection between two nodes in the graph.

    This is an abstract base class that should not be instantiated directly.

    Attributes:
        id (str): A unique identifier for the edge instance.
        from_node (NodePoolItem): The node from which the edge originates.
        to_node (NodePoolItem): The node to which the edge points.
        passes (int): The number of times the edge has been traversed.
        max_passes (int): The maximum number of times the edge can be traversed.
        edge_type (str): The type of the edge.
        edge_trace (EdgeTrace): The trace object for the edge.
    """
    def __init__(self, from_node: NodePoolItem, to_node: NodePoolItem = None, max_passes=25):
        """Initializes an Edge.

        Args:
            from_node (NodePoolItem): The node from which the edge originates.
            to_node (NodePoolItem, optional): The node to which the edge points.
                                          Defaults to None for conditional edges
                                          where the destination is determined
                                          at runtime.
            max_passes (int, optional): The maximum number of times the graph execution
                                    can traverse this edge. This helps prevent
                                    infinite loops. Defaults to 25.
        """
        self.id = "edge_" + str(uuid.uuid4())
        self.from_node = from_node
        self.to_node = to_node
        self.passes = 0
        self.max_passes = max_passes
        self.edge_type = None
        self.edge_trace = EdgeTrace(
            edge_id=self.id,
            edge_run_number=0,
            from_node=self.from_node.node.name,
            to_node=self.to_node.node.name if self.to_node else "N/A",
            passes_left=self.max_passes,
            edge_type=self.edge_type,
            elapsed=0.0,
            meta={}
        )

    def __repr__(self):
        return f"{self.__class__.__name__}({self.id})"

class ForwardEdge(Edge):
    """An edge that unconditionally forwards data and control from a source node
    to a destination node.
    """
    def __init__(self, from_node: NodePoolItem, to_node: NodePoolItem, max_passes: int = 25):
        """Initializes a ForwardEdge.

        Args:
            from_node (NodePoolItem): The node from which the edge originates.
            to_node (NodePoolItem): The node to which the edge points.
            max_passes (int, optional): The maximum number of times the graph execution
                                    can traverse this edge. Defaults to 25.
        """
        super().__init__(from_node, to_node, max_passes)
        self.edge_type = "__forward__"
        self.edge_trace = EdgeTrace(
            edge_id=self.id,
            edge_run_number=0,
            from_node=self.from_node.node.name,
            to_node=self.to_node.node.name if self.to_node else "N/A",
            passes_left=self.max_passes,
            edge_type=self.edge_type,
            elapsed=0.0,
            meta={
                "type": "forward_edge"
            })

class ConditionalEdge(Edge):
    """An edge that determines the next node based on the outcome of a gate function."""
    def __init__(
        self,
        from_node: NodePoolItem,
        gate_function: Callable,
        condition: Dict[str, str],
        max_passes=25
    ):
        """Initializes a ConditionalEdge.

        Args:
            from_node (NodePoolItem): The node from which the edge originates.
            gate_function (Callable): A function that is executed to decide which
                                  path to take. The function's return value is
                                  matched against the keys in the `condition`
                                  dictionary to determine the next node.
            condition (Dict[str, str]): A dictionary mapping the possible outcomes of the
                                    `gate_function` to the names of the next nodes.
            max_passes (int, optional): The maximum number of times the graph execution
                                    can traverse this edge. Defaults to 25.
        """
        super().__init__(from_node, to_node=None, max_passes=max_passes)  # initialize parent part
        self.gate_function = gate_function
        self.condition = condition
        self.edge_type = "__conditional__"
        self.edge_trace = EdgeTrace(
            edge_id=self.id,
            edge_run_number=0,
            from_node=self.from_node.node.name,
            to_node=self.to_node.node.name if self.to_node else "N/A",
            passes_left=self.max_passes,
            edge_type=self.edge_type,
            elapsed=0.0,
            meta={
                "type": "conditional_edge"
            }
        )

NodePoolItem.model_rebuild()
