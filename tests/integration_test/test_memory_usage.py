
import pytest
from typing import TypedDict, Dict
from orkes.graph.core import OrkesGraph
from memory_profiler import memory_usage
import os

# Define the state
class MemoryTestState(TypedDict):
    counter: int
    path: str

# Define node functions
def start_node(state: MemoryTestState) -> Dict:
    state['counter'] = 0
    state['path'] = "S"
    return state

def node_a(state: MemoryTestState) -> Dict:
    state['path'] += " -> A"
    state['counter'] += 1
    return state

def node_b(state: MemoryTestState) -> Dict:
    state['path'] += " -> B"
    return state

def should_loop(state: MemoryTestState) -> str:
    if state['counter'] < 100:
        return "LOOP"
    else:
        return "END"

def run_with_tracing():
    """Runs the graph with tracing enabled."""
    workflow = OrkesGraph(state=MemoryTestState, name="traced_graph", traced=True)
    workflow.add_node("start", start_node)
    workflow.add_node("A", node_a)
    workflow.add_node("B", node_b)
    workflow.add_edge(workflow.START, "start")
    workflow.add_edge("start", "A")
    workflow.add_edge("B", "A", max_passes=101)
    workflow.add_conditional_edge("A", should_loop, {
        "LOOP": "B",
        "END": "END"
    }, max_passes=101)
    app = workflow.compile()
    initial_state = {"counter": 0, "path": ""}
    app.run(initial_state)
    return app

def run_without_tracing():
    """Runs the graph with tracing disabled."""
    workflow = OrkesGraph(state=MemoryTestState, name="untraced_graph", traced=False)
    workflow.add_node("start", start_node)
    workflow.add_node("A", node_a)
    workflow.add_node("B", node_b)
    workflow.add_edge(workflow.START, "start")
    workflow.add_edge("start", "A")
    workflow.add_edge("B", "A", max_passes=101)
    workflow.add_conditional_edge("A", should_loop, {
        "LOOP": "B",
        "END": "END"
    }, max_passes=101)
    app = workflow.compile()
    initial_state = {"counter": 0, "path": ""}
    app.run(initial_state)
    return app

def test_memory_usage():
    """
    Measures and compares the memory usage of running the graph with and without tracing.
    """
    
    # Measure memory for traced execution
    mem_usage_traced = memory_usage((run_with_tracing, (), {}))
    traced_increment = max(mem_usage_traced) - min(mem_usage_traced)

    # Measure memory for untraced execution
    mem_usage_untraced = memory_usage((run_without_tracing, (), {}))
    untraced_increment = max(mem_usage_untraced) - min(mem_usage_untraced)

    print("\n" + "="*50)
    print("Memory Usage Comparison")
    print("="*50)
    print(f"Traced execution memory increment:     {traced_increment:.4f} MiB")
    print(f"Untraced execution memory increment:   {untraced_increment:.4f} MiB")
    print(f"Memory saved by disabling tracing:     {(traced_increment - untraced_increment):.4f} MiB")
    print("="*50)

    # Basic assertions to ensure the runs were different
    traced_app = run_with_tracing()
    untraced_app = run_without_tracing()
    assert traced_app.traced is True
    assert untraced_app.traced is False
    
    # Clean up trace files
    trace_file = f"traces/trace_{traced_app.run_id}_inspector.html"
    if os.path.exists(trace_file):
        os.remove(trace_file)
