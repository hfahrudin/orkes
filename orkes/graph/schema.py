from pydantic import BaseModel
from orkes.graph.unit import Node, Edge
from typing import Optional

class NodePoolItem(BaseModel):
    node: Node
    edge: Optional[Edge] = None
