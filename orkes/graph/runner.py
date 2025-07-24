
from typing import Callable, Any
from orkes.graph.unit import Node

class EdgeRunner:
    def __init__(self, edge):
        self.node = edge

    def run(self, *args, **kwargs) -> Any:
        """
        Executes the node's function with given arguments.

        Returns:
        - The result of the node's function execution.
        """
        result =  self.node.func(*args, **kwargs)
        return  result
    
class GraphRunner:
    def __init__(self, nodes, edges):
        self.nodes = nodes
        self.edges = edges



