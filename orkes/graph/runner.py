
import json
import time
import uuid
import os
from typing import Dict, Union, Optional
from orkes.graph.unit import ForwardEdge, ConditionalEdge
from orkes.graph.schema import NodePoolItem, TracesSchema, EdgeTrace
from orkes.graph.unit import _EndNode, _StartNode
from orkes.visualizer.generator import TraceInspector
from orkes.shared.context import trace_var, edge_id_var, edge_trace_var
from datetime import datetime

class GraphRunner:
    """Executes a compiled OrkesGraph, managing state and tracing the execution.

    The GraphRunner takes a compiled graph and an initial state, then traverses the
    graph, executing the nodes and updating the state accordingly. It also records
    traces of the execution, which can be saved to a file and visualized.

    Attributes:
        state_def (type): The TypedDict class that defines the shared state of the graph.
        nodes_pool (Dict[str, NodePoolItem]): A dictionary of all nodes in the graph.
        graph_state (Dict): The current state of the graph.
        run_id (str): A unique identifier for the current run.
        graph_name (str): The name of the graph being executed.
        graph_description (str): The description of the graph being executed.
        trace (TracesSchema): The trace of the current run.
        traces_dir (str): The directory where traces are saved.
        run_number (int): The current step number in the execution.
        auto_save_trace (bool): If True, the trace is automatically saved after execution.
        trace_inspector (TraceInspector): An object to generate a visualization of the trace.
    """

    def __init__(self, graph_name: str, graph_description: str, nodes_pool: Dict[str, NodePoolItem], graph_type: Dict, traces_dir: str = "traces", auto_save_trace: bool = False, traced: bool = True):
        """Initializes the GraphRunner.

        Args:
            graph_name (str): The name of the graph.
            graph_description (str): The description of the graph.
            nodes_pool (Dict[str, NodePoolItem]): The dictionary of nodes in the graph.
            graph_type (Dict): The TypedDict class that defines the shared state.
            traces_dir (str, optional): The directory to save traces. Defaults to "traces".
            auto_save_trace (bool, optional): Whether to automatically save traces.
                                            Defaults to False.
            traced (bool, optional): Whether to enable tracing. Defaults to True.
        """
        self.state_def = graph_type
        self.nodes_pool = nodes_pool
        self.graph_state: Dict = {}
        self.run_id = str(uuid.uuid4())
        self.graph_name = graph_name
        self.graph_description = graph_description
        self.traced = traced
        self.trace = None
        self.trace_inspector = None
        if self.traced:
            self.trace = TracesSchema(
                run_id=self.run_id,
                graph_name=self.graph_name,
                graph_description=self.graph_description,
                nodes_trace=[v.node.node_trace for k, v in nodes_pool.items()],
                edges_trace=[]
            )
            self.trace_inspector = TraceInspector()

        self.traces_dir = traces_dir
        self.run_number = 0
        self.auto_save_trace = auto_save_trace

    def save_run_trace(self):
        """Saves the execution trace to a JSON file."""
        if not self.traced:
            return
        if not os.path.exists(self.traces_dir):
            os.makedirs(self.traces_dir)
        filename = os.path.join(self.traces_dir, f"trace_{self.run_id}.json")
        with open(filename, 'w') as f:
            json.dump(self.trace.model_dump(), f, indent=4)

    def visualize_trace(self):
        """Generates an HTML visualization of the execution trace."""
        if not self.traced:
            return
        if not os.path.exists(self.traces_dir):
            os.makedirs(self.traces_dir)
        base_name = f"trace_{self.run_id}_inspector.html"
        out_file = os.path.join(self.traces_dir, base_name)
        self.trace_inspector.generate_viz(self.trace.model_dump(), out_file)

    def run(self, invoke_state: Dict) -> Dict:
        """Runs the graph with a given initial state.

        Args:
            invoke_state (Dict): The initial state to run the graph with.

        Returns:
            Dict: The final state of the graph after execution.

        Raises:
            KeyError: If the invoke_state contains keys not defined in the graph's state.
        """
        # Check that all keys in invoke_state exist in graph_state
        missing_keys = [key for key in invoke_state if key not in self.state_def.__annotations__]

        if missing_keys:
            raise KeyError(f"The following items are missing in self.graph_state: {missing_keys}")

        # Merge invoke_state into a copy of graph_state (avoid mutating original)
        self.graph_state = invoke_state
        input_state = self.graph_state.copy()

        # Start traversal from the START node
        start_pool = self.nodes_pool['START']
        start_edges = start_pool.edge

        if self.traced:
            self.trace.start_time = time.time()
            token = trace_var.set(self.trace)
            try:
                self.traverse_graph(start_edges, input_state)
            finally:
                trace_var.reset(token)

            self.trace.elapsed_time = time.time() - self.trace.start_time
            self.trace.status = "FINISHED"
            if self.auto_save_trace:
                self.save_run_trace()
        else:
            self.traverse_graph(start_edges, input_state)

        return self.graph_state

    def traverse_graph(self, current_edge: Union[ForwardEdge, ConditionalEdge], input_state: Dict):
        """Traverses the graph, either with or without tracing.

        Args:
            current_edge (Union[ForwardEdge, ConditionalEdge]): The current edge to traverse.
            input_state (Dict): The current state of the graph.
        """
        if self.traced:
            self._traverse_traced(current_edge, input_state)
        else:
            self._traverse_untraced(current_edge, input_state)

    def _traverse_untraced(self, current_edge: Union[ForwardEdge, ConditionalEdge], input_state: Dict):
        """Recursively traverses the graph without tracing.

        Args:
            current_edge (Union[ForwardEdge, ConditionalEdge]): The current edge to traverse.
            input_state (Dict): The current state of the graph.

        Raises:
            RuntimeError: If an edge is traversed more than the maximum allowed times.
        """
        if current_edge.passes > current_edge.max_passes:
            raise RuntimeError(
                f"Edge '{current_edge.id}' has been passed {current_edge.max_passes} times, "
                "exceeding the allowed maximum without reaching a stop condition."
            )
        else:
            current_edge.passes += 1

        current_node = current_edge.from_node.node
        if current_edge.edge_type == "__forward__":
            if not isinstance(current_node, _StartNode):
                result = current_node.execute(input_state)
                self.graph_state.update(result)

            next_edge = current_edge.to_node.edge
            next_node = current_edge.to_node.node
        elif current_edge.edge_type == "__conditional__":
            result = current_node.execute(input_state)
            self.graph_state.update(result)

            gate_function = current_edge.gate_function
            condition = current_edge.condition
            result_gate = gate_function(self.graph_state)

            next_node_name = condition[result_gate]

            next_node = self.nodes_pool[next_node_name].node
            next_edge = self.nodes_pool[next_node_name].edge

        if not isinstance(next_node, _EndNode):
            next_input = self.graph_state.copy()
            self.traverse_graph(next_edge, next_input)

    def _traverse_traced(self, current_edge: Union[ForwardEdge, ConditionalEdge], input_state: Dict):
        """Recursively traverses the graph with tracing.

        Args:
            current_edge (Union[ForwardEdge, ConditionalEdge]): The current edge to traverse.
            input_state (Dict): The current state of the graph.

        Raises:
            RuntimeError: If an edge is traversed more than the maximum allowed times.
        """
        edge_token = edge_id_var.set(current_edge.id)
        try:
            if current_edge.passes > current_edge.max_passes:
                raise RuntimeError(
                    f"Edge '{current_edge.id}' has been passed {current_edge.max_passes} times, "
                    "exceeding the allowed maximum without reaching a stop condition."
                )
            else:
                current_edge.passes += 1
                self.run_number += 1

            edge_trace = current_edge.edge_trace.model_copy()
            edge_trace.edge_run_number = self.run_number
            edge_trace.passes_left = current_edge.max_passes - current_edge.passes
            start = time.time()
            edge_trace.state_snapshot = input_state.copy()

            current_node = current_edge.from_node.node

            edge_trace_token = edge_trace_var.set(edge_trace)
            try:
                if current_edge.edge_type == "__forward__":
                    if not isinstance(current_node, _StartNode):
                        result = current_node.execute(input_state)
                        self.graph_state.update(result)

                    next_edge = current_edge.to_node.edge
                    next_node = current_edge.to_node.node
                elif current_edge.edge_type == "__conditional__":
                    result = current_node.execute(input_state)
                    self.graph_state.update(result)

                    gate_function = current_edge.gate_function
                    condition = current_edge.condition
                    result_gate = gate_function(self.graph_state)

                    next_node_name = condition[result_gate]

                    next_node = self.nodes_pool[next_node_name].node
                    next_edge = self.nodes_pool[next_node_name].edge
                    edge_trace.to_node = next_node_name
            finally:
                edge_trace_var.reset(edge_trace_token)

            edge_trace.elapsed = time.time() - start
            self.trace.edges_trace.append(edge_trace)

            if not isinstance(next_node, _EndNode):
                next_input = self.graph_state.copy()
                self.traverse_graph(next_edge, next_input)
        finally:
            edge_id_var.reset(edge_token)


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
