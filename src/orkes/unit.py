
from typing import List, Dict
from typing import Callable
import uuid

class Node:
    def __init__(self, name: str, func: Callable):
        """
        Initialize a Node.

        Parameters:
        - name (str): The unique identifier for the node.
        - name (func): The unique identifier for the node.
        """
        self.name: str = name
        self.func: str = func


    def __repr__(self) -> str:
        return f"Node({self.name})"


class ForwardEdge:
    def __init__(self, from_node: "Node", to_node: "Node"):
        """
        Initialize a ForwardEdge.

        Parameters:
        - from_node (Node): The source node of the edge.
        - to_node (Node): The destination node of the edge.
        """
        self.id: str = str(uuid.uuid4())
        self.origin: "Node" = from_node
        self.dest: "Node" = to_node

    def __repr__(self) -> str:
        return f"Node({self.id})"
    
class ConditionalEdge:
    def __init__(self, from_node: "Node", judge_func: Callable, condition: Dict):
        """
        Initialize a Node.

        Parameters:
        - name (str): The unique identifier for the node.
        - name (func): The unique identifier for the node.
        """
        self.id: str = str(uuid.uuid4())
        self.origin: "Node" = from_node
        self.mapper: Callable = judge_func
        self.condition : Dict = condition

    def __repr__(self) -> str:
        return f"Node({self.id})"