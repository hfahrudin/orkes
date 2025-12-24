from pydantic import BaseModel
from typing import Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from orkes.graph.unit import Node, Edge

class NodePoolItem(BaseModel):
    """
    Represents an item in the node pool, which is a collection of nodes and their
    associated edges within the graph. Each item encapsulates a node and an optional
    edge, defining a step in the graph's execution path.

    Attributes:
        node (Node): The node in the graph.
        edge (Optional[Union[Edge, str]]): The edge originating from the node.
                                           It can be an `Edge` object or a string
                                           identifier. Defaults to None if there's
                                           no outgoing edge from this node.
    """
    node: "Node"
    edge: Optional[Union["Edge", str]] = None

    model_config = {
        "arbitrary_types_allowed": True
    }

class NodeTrace(BaseModel):
    """
    Represents the trace of a single node's execution within the graph. It captures
    key information about the node for logging, debugging, and visualization purposes.

    Attributes:
        node_name (str): The name of the node.
        node_id (str): The unique identifier of the node.
        node_description (Optional[str]): A description of the node's function.
                                          Defaults to None.
        meta (dict): A dictionary for storing any additional metadata related to the
                     node, such as its type or properties.
    """
    node_name: str
    node_id: str
    node_description: Optional[str] = None
    meta: dict

class EdgeTrace(BaseModel):
    """
    Represents the trace of a single edge's traversal during the graph's execution.
    It records the flow of control between two nodes, providing insights into the
    graph's runtime behavior.

    Attributes:
        edge_id (str): The unique identifier of the edge.
        edge_run_number (int): The number of times this edge has been traversed in the
                               current run.
        from_node (str): The name of the node where the edge originates.
        to_node (str): The name of the node where the edge terminates.
        passes_left (int): The remaining number of times this edge can be traversed
                           before hitting its `max_passes` limit.
        edge_type (str): The type of the edge (e.g., '__forward__', '__conditional__').
        timestamp (float): The timestamp of when the edge was traversed.
        meta (dict): A dictionary for storing any additional metadata related to the
                     edge.
    """
    edge_id: str
    edge_run_number: int
    from_node: str
    to_node: str
    passes_left: int
    edge_type: Union[str, None]
    elapsed: float
    state_snapshot: dict = {}
    meta: dict

class TracesSchema(BaseModel):
    """
    Defines the schema for storing the complete trace of a graph's execution. It
    aggregates all the node and edge traces for a single run, providing a
    comprehensive record of the execution path.

    Attributes:
        run_id (str): The unique identifier for the graph execution run.
        nodes_trace (list[NodeTrace]): A list of all node traces recorded during the
                                       run.
        edges_trace (list[EdgeTrace]): A list of all edge traces recorded during the
                                       run.
    """
    graph_name : str
    run_id: str
    start_time: float = 0.0
    elapsed_time: float = 0.0
    status: str = "FAILED"
    nodes_trace: list[NodeTrace]
    edges_trace: list[EdgeTrace]
