import unittest
from typing import TypedDict, List
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

def aggregation_node(state: ComplexParallelGraphState) -> ComplexParallelGraphState:
    state['path'].append('aggregation')
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


if __name__ == "__main__":
    unittest.main()
