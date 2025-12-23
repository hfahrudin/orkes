from pydantic import BaseModel
from typing import Optional, TYPE_CHECKING, Union

if TYPE_CHECKING:
    from orkes.graph.unit import Node, Edge

class NodePoolItem(BaseModel):
    node: "Node"
    edge: Optional[Union["Edge", str]] = None

    model_config = {
        "arbitrary_types_allowed": True
    }

class NodeTrace(BaseModel):
    node_name: str
    node_id: str
    node_description: Optional[str] = None
    meta: dict

class EdgeTrace(BaseModel):
    edge_id: str
    edge_run_number: int
    from_node: str
    to_node: str
    max_passes: int
    edge_type: str
    timestamp: float
    meta: dict

class TracesSchema(BaseModel):
    run_id: str
    nodes_trace: list[NodeTrace]
    edges_trace: list[EdgeTrace]
