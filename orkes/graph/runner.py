import copy
import dataclasses
import logging
import time
import uuid
import os
from collections.abc import Mapping
from typing import Dict, Union, Optional
from orkes.graph.unit import ForwardEdge, ConditionalEdge
from orkes.graph.schema import NodePoolItem, TracesSchema
from orkes.shared.schema import to_dict, to_json
from orkes.graph.unit import _EndNode, _StartNode, AggregationNode
from orkes.visualizer.generator import TraceInspector
from orkes.shared.context import trace_var, edge_id_var, edge_trace_var

logger = logging.getLogger("orkes")

# Cap on a run's `error` text (message plus traceback), in bytes.
MAX_ERROR_BYTES = 8 * 1024


def _snapshot(state: Dict) -> Dict:
    """Copies state for a trace snapshot, deep so later in-place changes by
    other nodes don't alter it. Falls back to a shallow copy for state that
    can't be deep-copied (e.g. holds a lock or client object)."""
    try:
        return copy.deepcopy(state)
    except Exception:
        return dict(state)


def _describe_edge(edge) -> str:
    """A readable name for an edge, e.g. "conditional edge from 'loop'"."""
    kind = (edge.edge_type or "").strip("_")
    from_name = edge.from_node.node.name
    if edge.to_node is not None:
        return f"{kind} edge '{from_name}' -> '{edge.to_node.node.name}'"
    return f"{kind} edge from '{from_name}'"


def _format_error(error: BaseException) -> str:
    """The exception as "ExceptionType: message"."""
    return f"{type(error).__name__}: {error}"


def _format_error_with_traceback(error: BaseException) -> str:
    """"ExceptionType: message", a newline, then the traceback. Capped at
    MAX_ERROR_BYTES by cutting the oldest frames, so the line that raised stays."""
    import traceback  # imported here: only needed when a run fails

    header = _format_error(error)
    tb = "Traceback (most recent call last):\n" + "".join(traceback.format_tb(error.__traceback__))
    text = f"{header}\n{tb}"
    if len(text.encode()) <= MAX_ERROR_BYTES:
        return text
    prefix = f"{header}\n...\n"
    budget = MAX_ERROR_BYTES - len(prefix.encode())
    if budget <= 0:
        return header.encode()[:MAX_ERROR_BYTES].decode(errors="ignore")
    return prefix + tb.encode()[-budget:].decode(errors="ignore")


def _check_node_result(node, result) -> Dict:
    """Ensures a node returned a dict of state, with a clear error if not."""
    if not isinstance(result, Mapping):
        raise TypeError(
            f"Node '{node.name}' must return the state dict (or a dict of updates), "
            f"got {type(result).__name__}."
        )
    return result

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

    def __init__(self, graph_name: str, graph_description: str, nodes_pool: Dict[str, NodePoolItem], graph_type: Dict, traces_dir: str = "traces", auto_save_trace: bool = False, traced: bool = True, trace_sinks: Optional[list] = None):
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
            trace_sinks (list, optional): Objects that receive the trace as the
                run happens (see `orkes.exporters.TraceSink`).
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
            self.trace = self._new_trace()
            self.trace_inspector = TraceInspector()

        self.traces_dir = traces_dir
        self.run_number = 0
        self.auto_save_trace = auto_save_trace
        self._pending_branch_results = None
        # Per-run pass count for each edge, keyed by edge id. Kept on the
        # runner (not on the shared Edge objects) so separate compile()'d
        # runners and sequential runs never share counters.
        self._edge_passes: Dict[str, int] = {}
        self._failed_node: Optional[str] = None
        self.trace_sinks = list(trace_sinks or [])
        self._running = False
        self.has_async_components = self._compute_has_async_components(nodes_pool)

    def _new_trace(self) -> TracesSchema:
        """Builds an empty trace for the current `run_id`."""
        return TracesSchema(
            run_id=self.run_id,
            graph_name=self.graph_name,
            graph_description=self.graph_description,
            nodes_trace=[v.node.node_trace for v in self.nodes_pool.values()],
            edges_trace=[]
        )

    def _start_run(self, invoke_state: Dict) -> None:
        """Validates the input and resets all per-run state, so every call to
        `run()`/`arun()` is a separate run with its own id, trace and counters."""
        unknown_keys = [key for key in invoke_state if key not in self.state_def.__annotations__]
        if unknown_keys:
            raise KeyError(f"The following keys are not defined in the graph state: {unknown_keys}")

        self.run_id = str(uuid.uuid4())
        self.run_number = 0
        self._edge_passes = {}
        self._pending_branch_results = None
        self._failed_node = None
        # Copy so the caller's dict isn't modified in place.
        self.graph_state = dict(invoke_state)
        if self.traced:
            self.trace = self._new_trace()
            self.trace.start_time = time.time()

    def _end_run(self, error: Optional[BaseException]) -> None:
        """Records the final status, state, error and elapsed time of a traced run."""
        self.trace.final_state = _snapshot(self.graph_state)
        if error is None:
            self.trace.status = "FINISHED"
        else:
            self.trace.status = "FAILED"
            self.trace.error = _format_error_with_traceback(error)
            self.trace.failed_node = self._failed_node
        self.trace.elapsed_time = time.time() - self.trace.start_time
        if self.auto_save_trace:
            self.save_run_trace()

    def _notify_sinks(self, method: str, *args) -> None:
        """Calls `method` on every trace sink. A failing sink is logged and
        skipped, so it can never break the run."""
        for sink in self.trace_sinks:
            try:
                getattr(sink, method)(*args)
            except Exception:
                logger.warning("Trace sink %r failed in %s", sink, method, exc_info=True)

    def _timed_node(self, node, input_state, edge_trace) -> Dict:
        """Runs a node, recording only its own run time as `node_elapsed`."""
        start = time.perf_counter()
        result = self._execute_node(node, input_state)
        edge_trace.node_elapsed = time.perf_counter() - start
        return result

    async def _atimed_node(self, node, input_state, edge_trace) -> Dict:
        """Async counterpart to `_timed_node`; `edge_trace` is None when untraced."""
        start = time.perf_counter()
        result = await self._aexecute_node(node, input_state)
        if edge_trace is not None:
            edge_trace.node_elapsed = time.perf_counter() - start
        return result

    def _count_pass(self, edge) -> int:
        """Counts one traversal of `edge` in this run and returns the new count.

        Raises:
            RuntimeError: If the edge exceeds its `max_passes`.
        """
        passes = self._edge_passes.get(edge.id, 0) + 1
        if passes > edge.max_passes:
            raise RuntimeError(
                f"The {_describe_edge(edge)} was traversed more than its max_passes "
                f"limit of {edge.max_passes} without reaching a stop condition. "
                f"Check the loop's exit condition, or raise max_passes if it needs more passes."
            )
        self._edge_passes[edge.id] = passes
        return passes

    def _new_edge_trace(self, edge, passes: int, input_state: Dict):
        """Creates this traversal's own trace record for `edge`.

        Copied from the edge's template with fresh lists and dicts, so
        per-traversal data (`function_traces`, `llm_traces`, `meta`) is never
        shared between traversals.
        """
        self.run_number += 1
        template = edge.edge_trace
        edge_trace = dataclasses.replace(
            template,
            to_node=list(template.to_node) if isinstance(template.to_node, list) else template.to_node,
            meta=dict(template.meta),
            state_snapshot={},
            function_traces=[],
            llm_traces=[],
        )
        edge_trace.edge_run_number = self.run_number
        edge_trace.passes_left = edge.max_passes - passes
        edge_trace.state_snapshot = _snapshot(input_state)
        if isinstance(edge.from_node.node, _StartNode):
            edge_trace.node_elapsed = 0.0  # START runs no function
        return edge_trace

    @staticmethod
    def _compute_has_async_components(nodes_pool: Dict[str, NodePoolItem]) -> bool:
        """Checks whether any node function or conditional gate function in the
        graph is a coroutine function.

        Computed once at init so `run()` can fail fast -- before touching
        `self.graph_state` -- rather than discovering the mismatch deep inside
        execution after earlier nodes have already mutated state.
        """
        for node_pool_item in nodes_pool.values():
            if node_pool_item.node.is_async:
                return True
            edge = node_pool_item.edge
            if isinstance(edge, ConditionalEdge) and edge.is_async_gate:
                return True
        return False

    def save_run_trace(self):
        """Saves the execution trace to a JSON file."""
        if not self.traced:
            return
        if not os.path.exists(self.traces_dir):
            os.makedirs(self.traces_dir)
        filename = os.path.join(self.traces_dir, f"trace_{self.run_id}.json")
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(to_json(self.trace, indent=4))

    def visualize_trace(self):
        """Generates an HTML visualization of the execution trace."""
        if not self.traced:
            return
        if not os.path.exists(self.traces_dir):
            os.makedirs(self.traces_dir)
        base_name = f"trace_{self.run_id}_inspector.html"
        out_file = os.path.join(self.traces_dir, base_name)
        self.trace_inspector.generate_viz(to_dict(self.trace), out_file)

    def run(self, invoke_state: Dict) -> Dict:
        """Runs the graph with a given initial state.

        Args:
            invoke_state (Dict): The initial state to run the graph with.

        Returns:
            Dict: The final state of the graph after execution.

        Raises:
            KeyError: If the invoke_state contains keys not defined in the graph's state.
            RuntimeError: If the graph contains an async node/gate function --
                          use `arun()` instead. Also raised if this instance is
                          already executing a run -- each concurrent execution
                          needs its own `compile()`'d instance.
        """
        if self.has_async_components:
            raise RuntimeError(
                "This graph contains an async node function or async conditional "
                "gate function; use arun() instead of run()."
            )
        if self._running:
            raise RuntimeError(
                "This GraphRunner instance is already executing a run; each "
                "concurrent execution needs its own compile()'d instance -- "
                "e.g. [graph.compile() for _ in range(n)], not one instance "
                "reused across concurrent run()/arun() calls."
            )
        self._running = True
        try:
            self._start_run(invoke_state)
            start_edge = self.nodes_pool['START'].edge

            if not self.traced:
                self.traverse_graph(start_edge, self.graph_state.copy())
                return self.graph_state

            self._notify_sinks("on_run_start", self.trace)
            token = trace_var.set(self.trace)
            error = None
            try:
                self.traverse_graph(start_edge, self.graph_state.copy())
            except BaseException as e:
                error = e
                raise
            finally:
                trace_var.reset(token)
                self._end_run(error)
                self._notify_sinks("on_run_end", self.trace)

            return self.graph_state
        finally:
            self._running = False

    async def arun(self, invoke_state: Dict) -> Dict:
        """Runs the graph asynchronously with a given initial state.

        Unlike `run()`, this works for graphs with sync-only, async-only, or
        mixed node/gate functions -- sync functions are called directly (not
        offloaded to a thread), async functions are awaited.

        Args:
            invoke_state (Dict): The initial state to run the graph with.

        Returns:
            Dict: The final state of the graph after execution.

        Raises:
            KeyError: If the invoke_state contains keys not defined in the graph's state.
            RuntimeError: If this instance is already executing a run -- each
                          concurrent execution needs its own `compile()`'d
                          instance.
        """
        if self._running:
            raise RuntimeError(
                "This GraphRunner instance is already executing a run; each "
                "concurrent execution needs its own compile()'d instance -- "
                "e.g. [graph.compile() for _ in range(n)], not one instance "
                "reused across concurrent run()/arun() calls."
            )
        self._running = True
        try:
            self._start_run(invoke_state)
            start_edge = self.nodes_pool['START'].edge

            if not self.traced:
                await self.atraverse_graph(start_edge, self.graph_state.copy())
                return self.graph_state

            self._notify_sinks("on_run_start", self.trace)
            token = trace_var.set(self.trace)
            error = None
            try:
                await self.atraverse_graph(start_edge, self.graph_state.copy())
            except BaseException as e:
                error = e
                raise
            finally:
                trace_var.reset(token)
                self._end_run(error)
                if self.trace_sinks:
                    import asyncio  # imported here: keeps `import orkes.graph` light

                    # A sink may wait briefly to finish sending; keep that off the event loop.
                    await asyncio.to_thread(self._notify_sinks, "on_run_end", self.trace)

            return self.graph_state
        finally:
            self._running = False

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
            # Empty when the node is reached without going through its fork
            # (e.g. a loop back into it).
            branch_results = self._pending_branch_results or {}
            self._pending_branch_results = None
            return _check_node_result(node, node.execute(input_state, branch_results))
        return _check_node_result(node, node.execute(input_state))

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

    async def _aexecute_node(self, node, input_state) -> Dict:
        """Async counterpart to `_execute_node` -- awaits `node.aexecute(...)`,
        which itself handles sync and async node functions uniformly.
        """
        if isinstance(node, AggregationNode):
            branch_results = self._pending_branch_results or {}
            self._pending_branch_results = None
            return _check_node_result(node, await node.aexecute(input_state, branch_results))
        return _check_node_result(node, await node.aexecute(input_state))

    async def _arun_parallel_branches(self, current_edge) -> Dict[str, Dict]:
        """Async counterpart to `_run_parallel_branches`.

        Branches are still awaited one at a time, sequentially -- not via
        `asyncio.gather` -- so the existing swap-and-restore pattern on
        `self.graph_state` remains valid without further changes. True
        concurrent branch execution would require refactoring away from this
        shared-instance-state model and is out of scope here.
        """
        base_state = copy.deepcopy(self.graph_state)
        branch_results = {}
        for to_node_item in current_edge.to_nodes:
            branch_start_edge = self.nodes_pool[to_node_item.node.name].edge
            outer_graph_state = self.graph_state
            self.graph_state = copy.deepcopy(base_state)
            try:
                await self.atraverse_graph(branch_start_edge, self.graph_state.copy(), stop_node_name=current_edge.aggregation_node.node.name)
                branch_results[to_node_item.node.name] = self.graph_state
            finally:
                self.graph_state = outer_graph_state

        return branch_results

    async def atraverse_graph(self, current_edge: Union[ForwardEdge, ConditionalEdge], input_state: Dict, stop_node_name: Optional[str] = None):
        """Async counterpart to `traverse_graph`.

        A single method that branches internally on `self.traced` for the
        tracing-only bookkeeping, mirroring the shape of `_traverse_traced`
        while folding in the untraced case as a conditional -- rather than
        duplicating both existing sync methods into separate async copies.

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

            edge_token = edge_id_var.set(current_edge.id) if self.traced else None
            try:
                passes = self._count_pass(current_edge)

                edge_trace = None
                edge_trace_token = None
                start = None
                if self.traced:
                    edge_trace = self._new_edge_trace(current_edge, passes, input_state)
                    start = time.time()
                    edge_trace.started_at = start
                    edge_trace_token = edge_trace_var.set(edge_trace)

                try:
                    if current_edge.edge_type == "__forward__":
                        if not isinstance(current_node, _StartNode):
                            result = await self._atimed_node(current_node, input_state, edge_trace)
                            self.graph_state.update(result)

                        next_edge = current_edge.to_node.edge
                        next_node = current_edge.to_node.node
                    elif current_edge.edge_type == "__conditional__":
                        result = await self._atimed_node(current_node, input_state, edge_trace)
                        self.graph_state.update(result)

                        gate_function = current_edge.gate_function
                        condition = current_edge.condition
                        if current_edge.is_async_gate:
                            result_gate = await gate_function(self.graph_state)
                        else:
                            result_gate = gate_function(self.graph_state)
                        if result_gate not in condition:
                            raise KeyError(
                                f"Gate function on node '{current_node.name}' returned {result_gate!r}, "
                                f"which is not a valid key in its condition map {list(condition.keys())}."
                            )

                        next_node_name = condition[result_gate]

                        next_node = self.nodes_pool[next_node_name].node
                        next_edge = self.nodes_pool[next_node_name].edge
                        if self.traced:
                            edge_trace.to_node = next_node_name
                    elif current_edge.edge_type == "__parallel__":
                        if not isinstance(current_node, _StartNode):
                            result = await self._atimed_node(current_node, input_state, edge_trace)
                            self.graph_state.update(result)

                        if self.traced:
                            # Record the parallel branch starting points in the trace
                            edge_trace.to_node = [node_item.node.name for node_item in current_edge.to_nodes]
                            edge_trace.meta["aggregation_node"] = current_edge.aggregation_node.node.name

                        self._pending_branch_results = await self._arun_parallel_branches(current_edge)

                        # After all parallel branches are (sequentially) traversed,
                        # the control flow should move to the aggregation node.
                        next_node = current_edge.aggregation_node.node
                        next_edge = current_edge.aggregation_node.edge
                except BaseException as e:
                    if self.traced:
                        edge_trace.error = _format_error(e)
                    raise
                finally:
                    if self.traced:
                        edge_trace_var.reset(edge_trace_token)
                        # Recorded even on failure, so the failing edge shows in the trace.
                        edge_trace.elapsed = time.time() - start
                        self.trace.edges_trace.append(edge_trace)
                        if self.trace_sinks:
                            self._notify_sinks("on_edge", edge_trace)
            except BaseException:
                # Innermost edge wins: a failing branch is named, not its parallel edge.
                if self._failed_node is None:
                    self._failed_node = current_node.name
                raise
            finally:
                if self.traced:
                    edge_id_var.reset(edge_token)

            if isinstance(next_node, _EndNode):
                return

            current_edge = next_edge
            input_state = self.graph_state.copy()

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

            self._count_pass(current_edge)

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
                passes = self._count_pass(current_edge)
                edge_trace = self._new_edge_trace(current_edge, passes, input_state)
                start = time.time()
                edge_trace.started_at = start
                edge_trace_token = edge_trace_var.set(edge_trace)
                try:
                    if current_edge.edge_type == "__forward__":
                        if not isinstance(current_node, _StartNode):
                            result = self._timed_node(current_node, input_state, edge_trace)
                            self.graph_state.update(result)

                        next_edge = current_edge.to_node.edge
                        next_node = current_edge.to_node.node
                    elif current_edge.edge_type == "__conditional__":
                        result = self._timed_node(current_node, input_state, edge_trace)
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
                            result = self._timed_node(current_node, input_state, edge_trace)
                            self.graph_state.update(result)

                        # Record the parallel branch starting points in the trace
                        edge_trace.to_node = [node_item.node.name for node_item in current_edge.to_nodes]
                        edge_trace.meta["aggregation_node"] = current_edge.aggregation_node.node.name

                        self._pending_branch_results = self._run_parallel_branches(current_edge)

                        # After all parallel branches are (sequentially) traversed,
                        # the control flow should move to the aggregation node.
                        next_node = current_edge.aggregation_node.node
                        next_edge = current_edge.aggregation_node.edge
                except BaseException as e:
                    edge_trace.error = _format_error(e)
                    raise
                finally:
                    edge_trace_var.reset(edge_trace_token)
                    # Recorded even on failure, so the failing edge shows in the trace.
                    edge_trace.elapsed = time.time() - start
                    self.trace.edges_trace.append(edge_trace)
                    if self.trace_sinks:
                        self._notify_sinks("on_edge", edge_trace)
            except BaseException:
                # Innermost edge wins: a failing branch is named, not its parallel edge.
                if self._failed_node is None:
                    self._failed_node = current_node.name
                raise
            finally:
                edge_id_var.reset(edge_token)

            if isinstance(next_node, _EndNode):
                return

            current_edge = next_edge
            input_state = self.graph_state.copy()
