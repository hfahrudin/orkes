import time
from typing import TypedDict, List, Dict, Any
import json
import psutil
import os
import sys

# Orkes
from orkes.graph.core import OrkesGraph


# ------------------
# Shared State Definition
# ------------------
class GrowingState(TypedDict):
    iteration: int
    data: Dict[str, str]

# ------------------
# Helper to generate growing data
# ------------------
def generate_data(start_index: int, count: int) -> Dict[str, str]:
    return {f"key_{i}": f"value_{i}_" * 10 for i in range(start_index, start_index + count)}

# ------------------
# Orkes Implementation
# ------------------
def orkes_node_update_state(state: GrowingState, growth_per_iteration: int) -> GrowingState:
    current_data_size = len(state['data'])
    new_data = generate_data(current_data_size, growth_per_iteration)
    state['data'].update(new_data)
    state['iteration'] += 1
    return state

def build_orkes_graph():
    graph = OrkesGraph(state=GrowingState)
    return graph


if __name__ == "__main__":
    initial_data_size = 100
    num_iterations = 50
    growth_per_iteration = 1000 # Number of new key-value pairs added in each iteration

    print("Running Orkes Memory Benchmark...", file=sys.stderr)
    
    def orkes_update_closure(state: GrowingState):
        return orkes_node_update_state(state, growth_per_iteration)
    
    orkes_graph_builder = build_orkes_graph()
    orkes_graph_builder.add_node("update_state", orkes_update_closure)
    orkes_graph_builder.add_edge(orkes_graph_builder.START, "update_state")
    orkes_graph_builder.add_edge("update_state", orkes_graph_builder.END)
    orkes_compiled_graph = orkes_graph_builder.compile()

    orkes_memory_results = []
    pid = os.getpid()
    process = psutil.Process(pid)
    
    current_orkes_state = GrowingState(iteration=0, data=generate_data(0, initial_data_size))
    # Initial memory before first run
    mem_before_run = process.memory_info().rss / (1024 * 1024) # in MB
    orkes_memory_results.append({"iteration": 0, "state_size": initial_data_size, "memory_mb": mem_before_run, "execution_time_ms": 0})

    for i in range(num_iterations):
        # Reset edge passes for all relevant edges before each run
        for node_name, node_item in orkes_compiled_graph.nodes_pool.items():
            if node_item.edge and hasattr(node_item.edge, 'passes'):
                node_item.edge.passes = 0
        
        start_time = time.perf_counter()
        current_orkes_state = orkes_compiled_graph.run(current_orkes_state)
        end_time = time.perf_counter()
        execution_time_ms = (end_time - start_time) * 1000
        mem_usage_mb = process.memory_info().rss / (1024 * 1024) # in MB
        orkes_memory_results.append({
            "iteration": current_orkes_state['iteration'],
            "state_size": len(current_orkes_state['data']),
            "memory_mb": mem_usage_mb,
            "execution_time_ms": execution_time_ms
        })
    print(json.dumps({"orkes_memory_benchmark": orkes_memory_results}, indent=2))
