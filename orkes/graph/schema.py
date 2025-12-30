from pydantic import BaseModel
from typing import Optional, TYPE_CHECKING, Union, List, Dict, Any
from orkes.shared.schema import OrkesMessagesSchema, RequestSchema
from datetime import datetime

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

class LLMTraceSchema(BaseModel):
    """
    Represents the input and output of an LLM interaction for tracking purposes.

    Attributes:
        messages (OrkesMessagesSchema): The messages sent to the LLM.
        tools (Optional[List[Dict]]): The tools provided to the LLM.
        parsed_response (RequestSchema): The parsed response from the LLM.
        edge_id (Optional[str]): The ID of the graph edge that triggered this interaction.
        model (str): The name of the model used.
        settings (Optional[Dict]): Any additional settings used for the request.
    """
    messages: OrkesMessagesSchema
    tools: Optional[List[Dict]] = None
    parsed_response: RequestSchema
    model: str
    settings: Optional[Dict] = None


class FunctionTraceSchema(BaseModel):
    """
    Represents the trace of a single function's execution, capturing its inputs,
    output, and timing.

    Attributes:
        function_name (str): The name of the traced function.
        input_args (tuple): The positional arguments passed to the function.
        input_kwargs (dict): The keyword arguments passed to the function.
        return_value (Any): The value returned by the function.
        elapsed (float): The Unix timestamp when the function execution finished.
    """
    function_name: str
    input_args: tuple
    input_kwargs: dict
    return_value: Any
    elapsed: float

class EdgeTrace(BaseModel):
    """
    Represents the trace of a single edge traversal during a graph execution.

    This model captures when and how an edge was traversed, including execution
    order, timing information, and optional runtime metadata. It provides
    fine-grained visibility into control flow between nodes.

    Attributes:
        edge_id (str): Unique identifier of the edge.
        edge_run_number (int): Sequential number indicating how many times this edge
            has been traversed during the current run.
        from_node (str): Name of the source node where the edge originates.
        to_node (str): Name of the destination node where the edge terminates.
        passes_left (int): Remaining number of allowed traversals before the edge
            reaches its maximum pass limit.
        edge_type (str | None): Type of edge (e.g., "__forward__", "__conditional__").
        elapsed (float): Elapsed time in seconds since the start of the run when
            this edge was traversed.
        state_snapshot (dict): Snapshot of relevant runtime state at the moment
            the edge was traversed.
        meta (dict): Additional metadata associated with this edge traversal.
        llm_traces (list[LLMTraceSchema]): A list of LLM traces that occurred
                                           during this edge's execution.
        function_traces (list[FunctionTraceSchema]): A list of function traces
                                                     that occurred during this
                                                     edge's execution.
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
    function_traces: List[FunctionTraceSchema] = []
    llm_traces: List[LLMTraceSchema] = []


class TracesSchema(BaseModel):
    """
    Represents the complete execution trace of a graph run.

    This schema aggregates all node and edge traces for a single graph execution,
    along with execution metadata such as timing and status. It provides a
    comprehensive, ordered record of how the graph was executed.

    Attributes:
        graph_name (str): The name of the executed graph.
        graph_description (str): A description of the executed graph.   
        run_id (str): The unique identifier for this execution run.
        start_time (float): The Unix timestamp (in seconds) indicating when the
            execution started.
        elapsed_time (float): Total execution duration in seconds.
        status (str): Final execution status (e.g., "SUCCESS", "FAILED").
        nodes_trace (list[NodeTrace]): Traces for all nodes executed during the run.
        edges_trace (list[EdgeTrace]): Traces for all edges traversed during the run.
    """
    graph_name : str
    graph_description: str
    run_id: str
    start_time: float = 0.0
    elapsed_time: float = 0.0
    status: str = "FAILED"
    nodes_trace: list[NodeTrace]
    edges_trace: list[EdgeTrace]
