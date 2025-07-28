
from typing import Callable, Any, Dict
from orkes.graph.unit import Node,Edge
from orkes.graph.schema import NodePoolItem
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
    def __init__(self, nodes_pool: Dict[str, NodePoolItem], graph_state):
        self.graph_state = graph_state
        self.nodes_pool = nodes_pool

    #TODO: Modifications are returned as a new copy, not in-place mutation.
    def run(self, invoke_state):
        for key, value in invoke_state.items():
            if key in self.graph_state:
                self.graph_state[key] = value
        start_pool = self.nodes_pool['START']
        start_edges = start_pool.edge
        self.tranverse_graph( start_edges)

    #TODO: fix state only
    def tranverse_graph(self, current_edge: Edge):
        current_node = self.nodes_pool[current_edge.from_node].node
        result = current_node.execute()
        next_node = current_edge.to_node
        if current_edge.dest != END:
            self.tranverse_graph( current_node.dest, result)

