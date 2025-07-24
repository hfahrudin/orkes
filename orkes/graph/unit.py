
from typing import Any, Dict, Callable
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
        self.func: Callable = func

    def execute(self, state) -> Any:
        output = self.func(state)
        return output

    def __repr__(self) -> str:
        return f"Node({self.name})"
    

class ForwardEdge:
    def __init__(self, from_node: str, to_node: str, max_passes=5):
        """
        Initialize a ForwardEdge.

        Parameters:
        - from_node (Node): The source node of the edge.
        - to_node (Node): The destination node of the edge.
        """
        self.id: str = str(uuid.uuid4())
        self.origin: str = from_node
        self.dest: str = to_node
        self.passes = 0
        self.max_passes = max_passes

    def should_transfer(self, data: Any) -> bool:
        self.passes +=1
        return self.passes > self.max_passes
    
    def __repr__(self) -> str:
        return f"Edge({self.id})"
    
class ConditionalEdge:
    def __init__(self, from_node: str, judge_func: Callable, condition: Dict, max_passes=5):
        """
        Initialize a Node.
        """
        self.id: str = str(uuid.uuid4())
        self.origin: str = from_node
        self.mapper: Callable = judge_func
        self.condition : Dict = condition
        self.max_passes = max_passes

    def should_transfer(self, data: Any) -> bool:
        self.passes +=1
        return self.condition(data) and self.passes > self.max_passes
    
    def __repr__(self) -> str:
        return f"Node({self.id})"

#RUnner constarain for now: support fallback, condtional, :
# find Start Node:
# mapper: { Node:node, "to_edges" : []}
# was this edges conditional? if so what is the enxt edge
# get the edge
# each each propage:
# agrogator is not per se nodeits totally different or phantom node for aggregation edge