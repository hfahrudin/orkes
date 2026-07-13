

import copy
import json
import time
import uuid
import os
from typing import Dict, Union, Optional
from orkes.graph.unit import ForwardEdge, ConditionalEdge
from orkes.graph.schema import NodePoolItem, TracesSchema
from orkes.graph.unit import _EndNode, _StartNode, AggregationNode
from orkes.visualizer.generator import TraceInspector
from orkes.shared.context import trace_var, edge_id_var, edge_trace_var

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
        self._pending_branch_results = None

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

    def traverse_graph(self, current_edge: Union[ForwardEdge, ConditionalEdge], input_state: Dict, stop_node_name: Optional[str] = None):
        """Traverses the graph, either with or without tracing.

        Args:
            current_edge (Union[ForwardEdge, ConditionalEdge]): The current edge to traverse.
            input_state (Dict): The current state of the graph.
        """
        if self.traced:
            self._traverse_traced(current_edge, input_state, stop_node_name)
        else:
            self._traverse_untraced(current_edge, input_state, stop_node_name)

    def _execute_node(self, node, input_state) -> Dict:
        """Executes a node, passing along pending branch results if it's an
        `AggregationNode`.

        `_run_parallel_branches` computes branch results one loop iteration
        before the aggregation node is actually executed (it's just the
        `from_node` of the *next* edge at that point), so the pending
        results are handed off via `self._pending_branch_results` rather
        than a direct argument.
        """
        if isinstance(node, AggregationNode):
            branch_results = self._pending_branch_results
            self._pending_branch_results = None
            return node.execute(input_state, branch_results)
        return node.execute(input_state)

    def _run_parallel_branches(self, current_edge) -> Dict[str, Dict]:
        """Runs each parallel branch against its own isolated copy of the state.

        Every branch starts from a deep copy of the same snapshot (taken once,
        before any branch runs) rather than from whatever the previous branch
        happened to leave behind, and each branch's copy is independently deep
        -copied so in-place mutations (e.g. `state['x'].append(...)`) in one
        branch can never leak into another.

        Nothing is merged back into `graph_state` automatically -- the
        aggregation node receives the pre-fork state as its own input, plus
        every branch's independent final state (keyed by that branch's entry
        node name) if it opts in via a second parameter. It decides explicitly
        what survives.

        Returns:
            Dict[str, Dict]: Each branch's final state, keyed by the name of
                the node the branch started at.
        """
        base_state = copy.deepcopy(self.graph_state)
        branch_results = {}
        for to_node_item in current_edge.to_nodes:
            branch_start_edge = self.nodes_pool[to_node_item.node.name].edge
            outer_graph_state = self.graph_state
            self.graph_state = copy.deepcopy(base_state)
            try:
                self.traverse_graph(branch_start_edge, self.graph_state.copy(), stop_node_name=current_edge.aggregation_node.node.name)
                branch_results[to_node_item.node.name] = self.graph_state
            finally:
                self.graph_state = outer_graph_state

        return branch_results

    def _traverse_untraced(self, current_edge: Union[ForwardEdge, ConditionalEdge], input_state: Dict, stop_node_name: Optional[str] = None):
        """Iteratively traverses the graph without tracing.

        Each step's next edge/state is fed back into the loop rather than
        recursed into, so a long-running loop (many conditional-edge passes)
        doesn't grow the Python call stack and can't hit `RecursionError`.
        Only genuinely nested traversals -- parallel branches, which each
        start their own bounded call into `traverse_graph` -- still recurse.

        Args:
            current_edge (Union[ForwardEdge, ConditionalEdge]): The edge to start traversal from.
            input_state (Dict): The current state of the graph.
            stop_node_name (Optional[str]): The name of the node at which to stop traversal.

        Raises:
            RuntimeError: If an edge is traversed more than the maximum allowed times.
        """
        while True:
            current_node = current_edge.from_node.node
            if stop_node_name and current_node.name == stop_node_name:
                return

            current_edge.passes += 1
            if current_edge.passes > current_edge.max_passes:
                raise RuntimeError(
                    f"Edge '{current_edge.id}' has been passed {current_edge.max_passes} times, "
                    "exceeding the allowed maximum without reaching a stop condition."
                )

            if current_edge.edge_type == "__forward__":
                if not isinstance(current_node, _StartNode):
                    result = self._execute_node(current_node, input_state)
                    self.graph_state.update(result)

                next_edge = current_edge.to_node.edge
                next_node = current_edge.to_node.node
            elif current_edge.edge_type == "__conditional__":
                result = self._execute_node(current_node, input_state)
                self.graph_state.update(result)

                gate_function = current_edge.gate_function
                condition = current_edge.condition
                result_gate = gate_function(self.graph_state)
                if result_gate not in condition:
                    raise KeyError(
                        f"Gate function on node '{current_node.name}' returned {result_gate!r}, "
                        f"which is not a valid key in its condition map {list(condition.keys())}."
                    )

                next_node_name = condition[result_gate]

                next_node = self.nodes_pool[next_node_name].node
                next_edge = self.nodes_pool[next_node_name].edge
            elif current_edge.edge_type == "__parallel__":
                if not isinstance(current_node, _StartNode):
                    result = self._execute_node(current_node, input_state)
                    self.graph_state.update(result)

                self._pending_branch_results = self._run_parallel_branches(current_edge)

                # After all parallel branches are (sequentially) traversed,
                # the control flow should move to the aggregation node.
                # The 'next_edge' should be the one coming *out* of the aggregation node.
                next_node = current_edge.aggregation_node.node
                next_edge = current_edge.aggregation_node.edge

            if isinstance(next_node, _EndNode):
                return

            current_edge = next_edge
            input_state = self.graph_state.copy()

    def _traverse_traced(self, current_edge: Union[ForwardEdge, ConditionalEdge], input_state: Dict, stop_node_name: Optional[str] = None):
        """Iteratively traverses the graph with tracing.

        See `_traverse_untraced` for why this loops instead of recursing.
        `edge_id_var`/`edge_trace_var` are still set/reset once per edge, just
        within the loop body rather than across a recursive call, so LLM
        traces recorded during a node's execution still attach to the
        correct edge.

        Args:
            current_edge (Union[ForwardEdge, ConditionalEdge]): The edge to start traversal from.
            input_state (Dict): The current state of the graph.
            stop_node_name (Optional[str]): The name of the node at which to stop traversal.

        Raises:
            RuntimeError: If an edge is traversed more than the maximum allowed times.
        """
        while True:
            current_node = current_edge.from_node.node
            if stop_node_name and current_node.name == stop_node_name:
                return

            edge_token = edge_id_var.set(current_edge.id)
            try:
                current_edge.passes += 1
                if current_edge.passes > current_edge.max_passes:
                    raise RuntimeError(
                        f"Edge '{current_edge.id}' has been passed {current_edge.max_passes} times, "
                        "exceeding the allowed maximum without reaching a stop condition."
                    )
                self.run_number += 1

                edge_trace = current_edge.edge_trace.model_copy()
                edge_trace.edge_run_number = self.run_number
                edge_trace.passes_left = current_edge.max_passes - current_edge.passes
                start = time.time()
                edge_trace.state_snapshot = input_state.copy()

                edge_trace_token = edge_trace_var.set(edge_trace)
                try:
                    if current_edge.edge_type == "__forward__":
                        if not isinstance(current_node, _StartNode):
                            result = self._execute_node(current_node, input_state)
                            self.graph_state.update(result)

                        next_edge = current_edge.to_node.edge
                        next_node = current_edge.to_node.node
                    elif current_edge.edge_type == "__conditional__":
                        result = self._execute_node(current_node, input_state)
                        self.graph_state.update(result)

                        gate_function = current_edge.gate_function
                        condition = current_edge.condition
                        result_gate = gate_function(self.graph_state)
                        if result_gate not in condition:
                            raise KeyError(
                                f"Gate function on node '{current_node.name}' returned {result_gate!r}, "
                                f"which is not a valid key in its condition map {list(condition.keys())}."
                            )

                        next_node_name = condition[result_gate]

                        next_node = self.nodes_pool[next_node_name].node
                        next_edge = self.nodes_pool[next_node_name].edge
                        edge_trace.to_node = next_node_name
                    elif current_edge.edge_type == "__parallel__":
                        if not isinstance(current_node, _StartNode):
                            result = self._execute_node(current_node, input_state)
                            self.graph_state.update(result)

                        # Record the parallel branch starting points in the trace
                        edge_trace.to_node = [node_item.node.name for node_item in current_edge.to_nodes]
                        edge_trace.meta["aggregation_node"] = current_edge.aggregation_node.node.name

                        self._pending_branch_results = self._run_parallel_branches(current_edge)

                        # After all parallel branches are (sequentially) traversed,
                        # the control flow should move to the aggregation node.
                        next_node = current_edge.aggregation_node.node
                        next_edge = current_edge.aggregation_node.edge
                finally:
                    edge_trace_var.reset(edge_trace_token)

                edge_trace.elapsed = time.time() - start
                self.trace.edges_trace.append(edge_trace)
            finally:
                edge_id_var.reset(edge_token)

            if isinstance(next_node, _EndNode):
                return

            current_edge = next_edge
            input_state = self.graph_state.copy()
