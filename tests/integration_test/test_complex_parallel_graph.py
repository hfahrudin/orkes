import unittest
from typing import TypedDict, List, Dict
from orkes.graph import OrkesGraph

class ComplexParallelGraphState(TypedDict):
    path: List[str]
    branch_a_result: str
    branch_b_result: str
    branch_c_result: str
    aggregation_count: int

def start_node(state: ComplexParallelGraphState) -> ComplexParallelGraphState:
    state['path'].append('start')
    return state

def branch_a_start(state: ComplexParallelGraphState) -> ComplexParallelGraphState:
    state['path'].append('branch_a_start')
    state['branch_a_result'] = 'A'
    return state
    
def branch_a_end(state: ComplexParallelGraphState) -> ComplexParallelGraphState:
    state['path'].append('branch_a_end')
    return state

def branch_b_start(state: ComplexParallelGraphState) -> ComplexParallelGraphState:
    state['path'].append('branch_b_start')
    state['branch_b_result'] = 'B'
    return state

def branch_c_start(state: ComplexParallelGraphState) -> ComplexParallelGraphState:
    state['path'].append('branch_c_start')
    state['branch_c_result'] = 'C'
    return state

def aggregation_node(
    state: ComplexParallelGraphState,
    branch_results: Dict[str, ComplexParallelGraphState]
) -> ComplexParallelGraphState:
    # `state` is the pre-fork snapshot -- nothing branches wrote is merged in
    # automatically, so every field we want has to be pulled explicitly out
    # of `branch_results`, keyed by each branch's entry node name.
    prefork_len = len(state['path'])
    state['path'] = (
        state['path']
        + branch_results['branch_a_start']['path'][prefork_len:]
        + branch_results['branch_b_start']['path'][prefork_len:]
        + branch_results['branch_c_start']['path'][prefork_len:]
        + ['aggregation']
    )
    state['branch_a_result'] = branch_results['branch_a_start']['branch_a_result']
    state['branch_b_result'] = branch_results['branch_b_start']['branch_b_result']
    state['branch_c_result'] = branch_results['branch_c_start']['branch_c_result']
    state['aggregation_count'] += 1
    return state
    
def final_node(state: ComplexParallelGraphState) -> ComplexParallelGraphState:
    state['path'].append('final')
    return state


class TestComplexParallelGraph(unittest.TestCase):

    def setUp(self):
        self.graph = OrkesGraph(state=ComplexParallelGraphState)

        self.graph.add_node("start", start_node)
        self.graph.add_node("branch_a_start", branch_a_start)
        self.graph.add_node("branch_a_end", branch_a_end)
        self.graph.add_node("branch_b_start", branch_b_start)
        self.graph.add_node("branch_c_start", branch_c_start)
        self.graph.add_node("aggregation", aggregation_node)
        self.graph.add_node("final", final_node)

        self.graph.add_edge(self.graph.START, "start")
        
        self.graph.add_parallel_edges(
            from_node="start",
            to_nodes=["branch_a_start", "branch_b_start", "branch_c_start"],
            aggregation_node="aggregation"
        )
        
        self.graph.add_edge("branch_a_start", "branch_a_end")
        self.graph.add_edge("branch_a_end", "aggregation")
        self.graph.add_edge("branch_b_start", "aggregation")
        self.graph.add_edge("branch_c_start", "aggregation")

        self.graph.add_edge("aggregation", "final")
        self.graph.add_edge("final", self.graph.END)

    def test_complex_parallel_graph_execution_and_trace(self):
        compiled_graph = self.graph.compile()
        initial_state = {
            "path": [],
            "branch_a_result": "",
            "branch_b_result": "",
            "branch_c_result": "",
            "aggregation_count": 0,
        }
        final_state = compiled_graph.run(initial_state)

        # Flow correctness
        self.assertEqual(final_state['branch_a_result'], 'A')
        self.assertEqual(final_state['branch_b_result'], 'B')
        self.assertEqual(final_state['branch_c_result'], 'C')
        self.assertEqual(final_state['aggregation_count'], 1)
        
        expected_path = [
            'start', 
            'branch_a_start', 
            'branch_a_end', 
            'branch_b_start', 
            'branch_c_start', 
            'aggregation', 
            'final'
        ]
        
        self.assertCountEqual(final_state['path'], expected_path)
        self.assertEqual(len(final_state['path']), len(expected_path))


        # Trace correctness
        trace = compiled_graph.trace
        self.assertIsNotNone(trace)
        
        # Find the parallel edge trace
        parallel_edge_trace = None
        for edge_trace in trace.edges_trace:
            if edge_trace.from_node == 'start' and isinstance(edge_trace.to_node, list):
                parallel_edge_trace = edge_trace
                break
        
        self.assertIsNotNone(parallel_edge_trace, "Parallel edge trace not found")
        self.assertCountEqual(parallel_edge_trace.to_node, ["branch_a_start", "branch_b_start", "branch_c_start"])
        self.assertEqual(parallel_edge_trace.meta.get("aggregation_node"), "aggregation")

        # Check that branch A ran up to the aggregation node
        branch_a_end_trace = [t for t in trace.edges_trace if t.from_node == 'branch_a_end'][0]
        self.assertEqual(branch_a_end_trace.to_node, 'aggregation')

        # Check that branch B ran up to the aggregation node
        branch_b_start_trace = [t for t in trace.edges_trace if t.from_node == 'branch_b_start'][0]
        self.assertEqual(branch_b_start_trace.to_node, 'aggregation')
        
        # Check that branch C ran up to the aggregation node
        branch_c_start_trace = [t for t in trace.edges_trace if t.from_node == 'branch_c_start'][0]
        self.assertEqual(branch_c_start_trace.to_node, 'aggregation')

        # Check that aggregation node was not executed multiple times in the trace
        aggregation_traces = [t for t in trace.edges_trace if t.from_node == 'aggregation']
        self.assertEqual(len(aggregation_traces), 1)
        self.assertEqual(aggregation_traces[0].to_node, 'final')


class ParallelBranchIsolationState(TypedDict):
    shared_counter: int
    a_saw: int
    b_saw: int


def counter_start(state: ParallelBranchIsolationState) -> ParallelBranchIsolationState:
    return state


def counter_branch_a(state: ParallelBranchIsolationState) -> ParallelBranchIsolationState:
    state['a_saw'] = state['shared_counter']
    state['shared_counter'] += 1
    return state


def counter_branch_b(state: ParallelBranchIsolationState) -> ParallelBranchIsolationState:
    state['b_saw'] = state['shared_counter']
    state['shared_counter'] += 1
    return state


def counter_agg(
    state: ParallelBranchIsolationState,
    branch_results: Dict[str, ParallelBranchIsolationState]
) -> ParallelBranchIsolationState:
    # 'a_saw'/'b_saw' are disjoint per-branch keys, so pulling them from each
    # branch's own result is unambiguous. 'shared_counter' is a genuine
    # conflict (both branches wrote it) and is deliberately left untouched
    # here -- this test isn't about resolving that conflict.
    state['a_saw'] = branch_results['branch_a']['a_saw']
    state['b_saw'] = branch_results['branch_b']['b_saw']
    return state


class TestParallelBranchIsolation(unittest.TestCase):
    """Regression test: parallel branches must each see the state as it was at
    fan-out time, not whatever a previously-run sibling branch already wrote.
    Without isolation, branch order (insertion order of `to_nodes`) would
    silently change the result, which contradicts what "parallel" branches
    should mean."""

    def test_branches_do_not_observe_each_others_writes(self):
        graph = OrkesGraph(state=ParallelBranchIsolationState)
        graph.add_node("start", counter_start)
        graph.add_node("branch_a", counter_branch_a)
        graph.add_node("branch_b", counter_branch_b)
        graph.add_node("agg", counter_agg)

        graph.add_edge(graph.START, "start")
        graph.add_parallel_edges("start", ["branch_a", "branch_b"], "agg")
        graph.add_edge("branch_a", "agg")
        graph.add_edge("branch_b", "agg")
        graph.add_edge("agg", graph.END)

        app = graph.compile()
        final_state = app.run({"shared_counter": 0, "a_saw": -1, "b_saw": -1})

        # Both branches started from the same snapshot (counter == 0),
        # regardless of which one physically ran first. A naive merge that
        # re-applies each branch's *entire* dict (instead of just what it
        # changed) would let branch_b's untouched, stale copy of 'a_saw'
        # (-1, from before branch_a ran) clobber branch_a's real write.
        self.assertEqual(final_state['a_saw'], 0)
        self.assertEqual(final_state['b_saw'], 0)


class ParallelMutableStateIsolationState(TypedDict):
    shared_log: List[str]
    a_saw_len: int
    b_saw_len: int


def mutable_start(state: ParallelMutableStateIsolationState) -> ParallelMutableStateIsolationState:
    return state


def mutable_branch_a(state: ParallelMutableStateIsolationState) -> ParallelMutableStateIsolationState:
    state['a_saw_len'] = len(state['shared_log'])
    state['shared_log'].append('A')
    return state


def mutable_branch_b(state: ParallelMutableStateIsolationState) -> ParallelMutableStateIsolationState:
    state['b_saw_len'] = len(state['shared_log'])
    state['shared_log'].append('B')
    return state


def mutable_agg(
    state: ParallelMutableStateIsolationState,
    branch_results: Dict[str, ParallelMutableStateIsolationState]
) -> ParallelMutableStateIsolationState:
    # 'shared_log' is a genuine conflict key -- both branches appended to it.
    # There's no automatic merge, so the aggregation node must explicitly
    # choose what survives; here we deliberately keep only branch_a's list.
    state['a_saw_len'] = branch_results['branch_a']['a_saw_len']
    state['b_saw_len'] = branch_results['branch_b']['b_saw_len']
    state['shared_log'] = branch_results['branch_a']['shared_log']
    return state


class TestParallelBranchMutableStateIsolation(unittest.TestCase):
    """Regression test for a shallow-copy bug: `dict.copy()` at fan-out only
    copies the top-level dict, so a mutable value (e.g. a list) under a state
    key was the *same object* shared by every branch's supposedly-isolated
    copy. An in-place mutation (`list.append`, the idiom this library's own
    docs teach) in one branch was therefore visible to every sibling branch
    that ran afterward, silently defeating isolation. Fixed by deep-copying
    the state at each fork point in `_run_parallel_branches`."""

    def test_branch_does_not_see_siblings_in_place_mutation(self):
        graph = OrkesGraph(state=ParallelMutableStateIsolationState)
        graph.add_node("start", mutable_start)
        graph.add_node("branch_a", mutable_branch_a)
        graph.add_node("branch_b", mutable_branch_b)
        graph.add_node("agg", mutable_agg)

        graph.add_edge(graph.START, "start")
        graph.add_parallel_edges("start", ["branch_a", "branch_b"], "agg")
        graph.add_edge("branch_a", "agg")
        graph.add_edge("branch_b", "agg")
        graph.add_edge("agg", graph.END)

        app = graph.compile()
        final_state = app.run({"shared_log": [], "a_saw_len": -1, "b_saw_len": -1})

        # Both branches must observe the pre-fork list (length 0), regardless
        # of execution order. With the aliasing bug, branch_b (which runs
        # second) would see length 1 because branch_a's append had already
        # mutated the list object both branches secretly shared.
        self.assertEqual(final_state['a_saw_len'], 0)
        self.assertEqual(final_state['b_saw_len'], 0)

        # Each branch must have appended to its own independent list. With
        # the aliasing bug, both appends land on the same object, producing
        # ['A', 'B'] instead of the last writer's single-item list.
        self.assertEqual(len(final_state['shared_log']), 1)


class OneParamAggState(TypedDict):
    branch_a_value: str
    branch_b_value: str


def one_param_start(state: OneParamAggState) -> OneParamAggState:
    return state


def one_param_branch_a(state: OneParamAggState) -> OneParamAggState:
    state['branch_a_value'] = 'A'
    return state


def one_param_branch_b(state: OneParamAggState) -> OneParamAggState:
    state['branch_b_value'] = 'B'
    return state


def one_param_agg(state: OneParamAggState) -> OneParamAggState:
    """Invalid as an aggregation node: doesn't declare `branch_results` at
    all, so compile() cannot tell whether discarding branch output here is
    intentional or accidental."""
    return state


def two_param_agg_ignoring_results(state: OneParamAggState, branch_results) -> OneParamAggState:
    """Valid: declares `branch_results`, but the body chooses not to use
    it. Discarding branch output is fine -- it just has to be an explicit,
    visible choice in the signature, not an accident of writing a node the
    same way as any other node in the graph."""
    return state


class TestAggregationNodeSignature(unittest.TestCase):
    """compile() must raise when an aggregation node doesn't declare a
    `branch_results` parameter, since a ParallelEdge never auto-merges
    branch state back -- without that parameter there is no way for the
    node to see (or deliberately ignore) what each branch produced, so any
    branch's state changes are silently lost. Whether the function body
    actually *uses* branch_results is not policed -- ignoring it on purpose
    is a valid, explicit choice once the parameter exists."""

    def _build_graph(self, agg_func):
        graph = OrkesGraph(state=OneParamAggState)
        graph.add_node("start", one_param_start)
        graph.add_node("branch_a", one_param_branch_a)
        graph.add_node("branch_b", one_param_branch_b)
        graph.add_node("agg", agg_func)

        graph.add_edge(graph.START, "start")
        graph.add_parallel_edges("start", ["branch_a", "branch_b"], "agg")
        graph.add_edge("branch_a", "agg")
        graph.add_edge("branch_b", "agg")
        graph.add_edge("agg", graph.END)
        return graph

    def test_compile_raises_when_aggregation_node_does_not_accept_branch_results(self):
        graph = self._build_graph(one_param_agg)
        with self.assertRaisesRegex(TypeError, "branch_results"):
            graph.compile()

    def test_two_param_aggregation_node_ignoring_branch_results_is_allowed(self):
        graph = self._build_graph(two_param_agg_ignoring_results)
        app = graph.compile()  # must not raise -- the parameter is declared
        final_state = app.run({"branch_a_value": "", "branch_b_value": ""})

        # Discarding branch output is allowed -- init_state is returned
        # untouched since the function never reads branch_results.
        self.assertEqual(final_state['branch_a_value'], "")
        self.assertEqual(final_state['branch_b_value'], "")

    def test_two_param_aggregation_node_does_not_raise(self):
        graph = OrkesGraph(state=ParallelBranchIsolationState)
        graph.add_node("start", counter_start)
        graph.add_node("branch_a", counter_branch_a)
        graph.add_node("branch_b", counter_branch_b)
        graph.add_node("agg", counter_agg)

        graph.add_edge(graph.START, "start")
        graph.add_parallel_edges("start", ["branch_a", "branch_b"], "agg")
        graph.add_edge("branch_a", "agg")
        graph.add_edge("branch_b", "agg")
        graph.add_edge("agg", graph.END)

        graph.compile()  # must not raise -- counter_agg uses branch_results


if __name__ == "__main__":
    unittest.main()
