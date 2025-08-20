
from typing import Callable, Any, Dict
from orkes.graph.unit import Node,Edge
from orkes.graph.schema import NodePoolItem
from orkes.graph.unit import _EndNode, _StartNode

class GraphRunner:
    def __init__(self, nodes_pool: Dict[str, NodePoolItem], graph_type: Dict):
        self.state_def = graph_type
        self.nodes_pool = nodes_pool
        self.graph_state: Dict = {}

    #TODO: Modifications are returned as a new copy, not in-place mutation.
    def run(self, invoke_state):
        # Check that all keys in invoke_state exist in graph_state
        missing_keys = [key for key in invoke_state if key not in self.state_def.__annotations__]

        if missing_keys:
            raise KeyError(f"The following items are missing in self.graph_state: {missing_keys}")

        # Merge invoke_state into a copy of graph_state (avoid mutating original)
        self.graph_state = invoke_state
        input_state = self.graph_state.copy()
        # Start traversal
        start_pool = self.nodes_pool['START']
        start_edges = start_pool.edge
        self.traverse_graph(start_edges, input_state)
        return self.graph_state

    #TODO: fix state only
    def traverse_graph(self, current_edge: Edge, input_state: Dict):

        if current_edge.edge_type == "__forward__":
            print(f"I am here on forward edge {current_edge.id}")
        elif current_edge.edge_type == "__conditional__":
            print(f"I am here on conditional edge {current_edge.id}")

        current_node = current_edge.from_node.node
        if not isinstance(current_node, _StartNode):
            result =  current_node.execute(input_state)
            self.graph_state.update(result)
        
        next_edge = current_edge.to_node.edge
        next_node = current_edge.to_node.node


        # result = current_node.execute(input_state)
        # next_node = current_node.edge
        if not isinstance(next_node, _EndNode):
            next_input = self.graph_state.copy()
            self.traverse_graph( next_edge, next_input)



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