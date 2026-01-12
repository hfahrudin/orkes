import time
from typing import TypedDict, List
from memory_profiler import memory_usage
import json

# LangGraph
from langgraph.graph import StateGraph, END


# ------------------
# Shared State
# ------------------
class BenchmarkState(TypedDict):
    value: int
    value_c: int
    history: List[str]


# ------------------
# LangGraph Implementation
# ------------------
def langgraph_node_a(state: BenchmarkState) -> BenchmarkState:
    state['value'] += 1
    state['history'].append('A')
    return state

def langgraph_node_b(state: BenchmarkState) -> BenchmarkState:
    state['value'] += 1
    state['history'].append('B')
    return state

    
def langgraph_gate(state: BenchmarkState) -> str:
    if state['value'] > 5:
        return 'end'
    else:
        return 'continue'

def build_langgraph_graph():
    graph = StateGraph(BenchmarkState)
    graph.add_node("A", langgraph_node_a)
    graph.add_node("B", langgraph_node_b)
    graph.set_entry_point("A")
    graph.add_conditional_edges(
        "A",
        langgraph_gate,
        {
            "continue": "B",
            "end": END,
        },
    )
    graph.add_edge("B", "A")
    return graph.compile()


# ------------------
# Benchmark Execution
# ------------------
def run_langgraph_benchmark(langgraph_graph):
    initial_state = {"value": 0, "value_c": 0, "history": []}
    langgraph_graph.invoke(initial_state)


if __name__ == "__main__":
    # Build graph
    langgraph_graph_compiled = build_langgraph_graph()

    # Time Benchmark
    start_time = time.time()
    run_langgraph_benchmark(langgraph_graph_compiled)
    langgraph_time = time.time() - start_time

    # Memory Benchmark
    langgraph_mem = memory_usage((run_langgraph_benchmark, (langgraph_graph_compiled,)), max_usage=True)

    # Output results as JSON
    results = {
        "time": langgraph_time,
        "memory": langgraph_mem
    }
    print(json.dumps(results))
