
import json
import time
import uuid
import os
from typing import Dict, Union, Optional
from orkes.graph.unit import ForwardEdge, ConditionalEdge
from orkes.graph.schema import NodePoolItem, TracesSchema, EdgeTrace
from orkes.graph.unit import _EndNode, _StartNode

class GraphRunner:
    def __init__(self, graph_name:str, nodes_pool: Dict[str, NodePoolItem], graph_type: Dict, traces_dir:str = "traces"):
        self.state_def = graph_type
        self.nodes_pool = nodes_pool
        self.graph_state: Dict = {}
        self.run_id = str(uuid.uuid4())
        self.graph_name = graph_name
        self.trace = TracesSchema(
            run_id=self.run_id,
            graph_name=self.graph_name,
            nodes_trace=[v.node.node_trace for k, v in nodes_pool.items()],
            edges_trace=[]
        )
        self.traces_dir = traces_dir
        self.run_number = 0

    def save_run_trace(self):
        if not os.path.exists(self.traces_dir):
            os.makedirs(self.traces_dir)
        filename = os.path.join(self.traces_dir, f"trace_{self.run_id}.json")
        with open(filename, 'w') as f:
            json.dump(self.trace.model_dump(), f, indent=4)

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
        
        self.trace.start_time = time.time()

        self.traverse_graph(start_edges, input_state)
        
        self.trace.elapsed_time = time.time() - self.trace.start_time
        self.trace.status = "FINISHED"

        self.save_run_trace()
        return self.graph_state

    def traverse_graph(self, current_edge: Union[ForwardEdge, ConditionalEdge], input_state: Dict):

        if current_edge.passes > current_edge.max_passes:
            raise RuntimeError(
                f"Edge '{current_edge.id}' has been passed {current_edge.max_passes} times, "
                "exceeding the allowed maximum without reaching a stop condition."
            )
        else:
            current_edge.passes+=1
            self.run_number += 1

        edge_trace = current_edge.edge_trace.model_copy()
        edge_trace.edge_run_number = self.run_number 
        edge_trace.passes_left = current_edge.max_passes - current_edge.passes
        start = time.time()
        edge_trace.state_snapshot = input_state.copy()


        current_node = current_edge.from_node.node
        
        if current_edge.edge_type == "__forward__":
            if not isinstance(current_node, _StartNode):
                result =  current_node.execute(input_state)
                self.graph_state.update(result)

            next_edge = current_edge.to_node.edge
            next_node = current_edge.to_node.node


        elif current_edge.edge_type == "__conditional__":
            result =  current_node.execute(input_state)
            self.graph_state.update(result)

            gate_function = current_edge.gate_function
            condition = current_edge.condition
            result_gate = gate_function(self.graph_state)

            next_node_name = condition[result_gate]
            
            next_node = self.nodes_pool[next_node_name].node
            next_edge = self.nodes_pool[next_node_name].edge
            edge_trace.to_node = next_node_name
        edge_trace.elapsed = time.time() - start
        self.trace.edges_trace.append(edge_trace)
        
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
