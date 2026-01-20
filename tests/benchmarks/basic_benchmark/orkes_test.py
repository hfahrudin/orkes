import time
from typing import TypedDict, List
from memory_profiler import memory_usage
import json

# Orkes
from orkes.graph.core import OrkesGraph


# ------------------
# Shared State
# ------------------
class BenchmarkState(TypedDict):
    value: int
    history: List[str]


# ------------------
# Orkes Implementation
# ------------------
def orkes_node_a(state: BenchmarkState) -> BenchmarkState:
    state['value'] += 1
    state['history'].append('A')
    return state

def orkes_node_b(state: BenchmarkState) -> BenchmarkState:
    state['value'] *= 2
    state['history'].append('B')
    return state

def orkes_gate(state: BenchmarkState) -> str:
    if state['value'] > 5:
        return 'end'
    else:
        return 'continue'

def build_orkes_graph():
    graph = OrkesGraph(state=BenchmarkState)
    graph.add_node("A", orkes_node_a)
    graph.add_node("B", orkes_node_b)
    graph.add_edge(graph.START, "A")
    graph.add_conditional_edge(
        "A",
        orkes_gate,
        {
            "continue": "B",
            "end": "END",
        },
    )
    graph.add_edge("B", "A")
    return graph.compile()


# ------------------
# Benchmark Execution
# ------------------
def run_orkes_benchmark(orkes_graph):
    initial_state = {"value": 0, "history": []}
    orkes_graph.run(initial_state)


if __name__ == "__main__":
    # Build graph
    orkes_graph_compiled = build_orkes_graph()
    
    # Time Benchmark
    start = time.perf_counter()
    run_orkes_benchmark(orkes_graph_compiled)
    orkes_time = time.perf_counter() - start

    # Memory Benchmark
    orkes_mem = memory_usage((run_orkes_benchmark, (orkes_graph_compiled,)), max_usage=True)

    # Output results as JSON
    results = {
        "time": orkes_time,
        "memory": orkes_mem
    }
    print(json.dumps(results))
