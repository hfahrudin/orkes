
from typing import Callable, Any
from orkes.graph.unit import Node, START, END, Edge

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
    def __init__(self, nodes_pool, edges_pool):
        self.nodes_pool = nodes_pool
        self.edges_pool = edges_pool

    def run(self, query):

        start_edges = self.edges_pool['START']

    def tranverse_graph(self, current_edge: Edge, query):
        current_node = self.nodes_pool[current_edge.from_node]["node"]
        result = current_node.execute(query)
        next_node = current_edge.to_node
        if current_edge.dest != END:
            self.tranverse_graph( current_node.dest, result)

