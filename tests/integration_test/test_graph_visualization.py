import os
import pytest
from typing import TypedDict, Dict
from orkes.graph.core import OrkesGraph

# 1. Define the state
class GraphState(TypedDict):
    input: str
    output: str
    path: str

# 2. Define node functions
def node_a(state: GraphState) -> Dict:
    state['output'] = state['input'] + " -> A"
    state['path'] += "A"
    return state

def node_b(state: GraphState) -> Dict:
    state['output'] = state['output'] + " -> B"
    state['path'] += "B"
    return state

def should_go_to_c(state: GraphState) -> str:
    if "A" in state['path']:
        return "C"
    else:
        return "D"

def node_c(state: GraphState) -> Dict:
    state['output'] += " -> C"
    state['path'] += "C"
    return state

def node_d(state: GraphState) -> Dict:
    state['output'] += " -> D"
    state['path'] += "D"
    return state


def test_graph_visualization():
    """
    Tests the graph running and visualization generation.
    """
    # 3. Create a graph
    workflow = OrkesGraph(state=GraphState, name="test_graph")

    # 4. Add nodes
    workflow.add_node("A", node_a)
    workflow.add_node("B", node_b)
    workflow.add_node("C", node_c)
    workflow.add_node("D", node_d)


    # 5. Add edges
    workflow.add_edge(workflow.START, "A")
    workflow.add_edge("A", "B")
    workflow.add_conditional_edge("B", should_go_to_c, {
        "C": "C",
        "D": "D"
    })
    workflow.add_edge("C", workflow.END)
    workflow.add_edge("D", workflow.END)

    # 6. Compile the graph
    app = workflow.compile()

    # 7. Run the graph
    initial_state = {"input": "start", "output": "", "path": ""}
    final_state = app.run(initial_state)

    # 8. Generate visualization
    app.visualize_trace()

    # 9. Assertions
    trace_file = f"traces/trace_{app.run_id}_inspector.html"
    assert os.path.exists(trace_file)
    assert "start -> A -> B -> C" == final_state.get("output")
    assert "ABC" == final_state.get("path")

    # 9.1. Assert trace data
    trace_data = app.trace
    assert trace_data.status == "FINISHED"
    assert len(trace_data.nodes_trace) == 6 # START, A, B, C, D, END
    assert len(trace_data.edges_trace) == 4 # START -> A, A -> B, B -> C, C -> END

    # 9.2. Assert node execution order
    executed_nodes = [edge.from_node for edge in trace_data.edges_trace]
    assert executed_nodes == ['START', 'A', 'B', 'C']

    # 10. Clean up the generated file
    os.remove(trace_file)
