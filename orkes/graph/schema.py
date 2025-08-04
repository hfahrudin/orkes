from pydantic import BaseModel
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from orkes.graph.unit import Node, Edge

class NodePoolItem(BaseModel):
    node: "Node"
    edge: Optional["Edge"] = None

    model_config = {
        "arbitrary_types_allowed": True
    }