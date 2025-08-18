
from typing import Callable, Any, Dict
from orkes.graph.unit import Node,Edge
from orkes.graph.schema import NodePoolItem
from orkes.graph.unit import _EndNode

class GraphRunner:
    def __init__(self, nodes_pool: Dict[str, NodePoolItem], graph_state: Dict):
        self.graph_state = graph_state
        self.nodes_pool = nodes_pool

    #TODO: Modifications are returned as a new copy, not in-place mutation.
    def run(self, invoke_state):
        # Check that all keys in invoke_state exist in graph_state
        missing_keys = [key for key in invoke_state if key not in self.graph_state]
        if missing_keys:
            raise KeyError(f"The following items are missing in self.graph_state: {missing_keys}")

        # Merge invoke_state into a copy of graph_state (avoid mutating original)
        input_state = self.graph_state.copy()
        input_state.update({k: v for k, v in invoke_state.items() if k in input_state})

        # Start traversal
        start_pool = self.nodes_pool['START']
        start_edges = start_pool.edge
        state = self.traverse_graph(start_edges, input_state)
        return state

    #TODO: fix state only
    def traverse_graph(self, current_edge: Edge, input_state: Dict):
        current_node = self.nodes_pool[current_edge.from_node].node
        result = current_node.execute(input_state)
        next_node = current_edge.to_node
        if not isinstance(next_node, _EndNode):
            result = self.traverse_graph( next_node, result)
        else:
            return result



# Handle Brancing and merging state -> because state update only happen after node process done, no shared mutable object
# FAN IN FAN OUT STRATEGY, EVERY BRANCHING NODE NEED TO BE RETURNED
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