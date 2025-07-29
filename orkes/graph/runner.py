
from typing import Callable, Any, Dict
from orkes.graph.unit import Node,Edge
from orkes.graph.schema import NodePoolItem

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



# Handle Brancing and merging state -> because state update only happen after everything done, no shared mutable object
# In your example:
#     A
#     |
#     B
#    / \
#   C   D
#        \
#         E
# If E needs data from both C and D, you have two main options:

# Make E a "merge node" that accepts inputs from both C and D — i.e., edges C -> E and D -> E.

# E will receive two incoming states, merge them internally, then execute.

# Insert an explicit merge node (e.g., M):

#     C   D
#      \ /
#       M
#       |
#       E
# The merge node M merges C and D’s outputs.

# Then E runs with the combined state.