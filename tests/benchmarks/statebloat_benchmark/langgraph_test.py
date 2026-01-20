import time
from typing import TypedDict, List, Dict, Any
import json
import psutil
import os
import sys

# Langchain
from langgraph.graph import StateGraph, END


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
# Langgraph Implementation
# ------------------
def langgraph_node_update_state(state: GrowingState, growth_per_iteration: int) -> GrowingState:
    current_data_size = len(state['data'])
    new_data = generate_data(current_data_size, growth_per_iteration)
    state['data'].update(new_data)
    state['iteration'] += 1
    return state

def build_langgraph_workflow():
    workflow = StateGraph(GrowingState)
    return workflow


if __name__ == "__main__":
    initial_data_size = 100
    num_iterations = 50
    growth_per_iteration = 1000 # Number of new key-value pairs added in each iteration

    print("Running Langgraph Memory Benchmark...", file=sys.stderr)
    # --- Langgraph Benchmark ---
    def langgraph_update_closure(state: GrowingState):
        return langgraph_node_update_state(state, growth_per_iteration)

    langgraph_workflow_builder = build_langgraph_workflow()
    langgraph_workflow_builder.add_node("update_state", langgraph_update_closure)
    langgraph_workflow_builder.set_entry_point("update_state")
    langgraph_workflow_builder.add_edge("update_state", END)
    langgraph_app = langgraph_workflow_builder.compile()

    langgraph_memory_results = []
    pid = os.getpid() # Use the same PID for memory tracking within this script
    process = psutil.Process(pid)
    
    current_langgraph_state = GrowingState(iteration=0, data=generate_data(0, initial_data_size))
    # Initial memory before first run
    mem_before_run = process.memory_info().rss / (1024 * 1024) # in MB
    langgraph_memory_results.append({"iteration": 0, "state_size": initial_data_size, "memory_mb": mem_before_run, "execution_time_ms": 0})

    for i in range(num_iterations):
        start_time = time.perf_counter()
        current_langgraph_state = langgraph_app.invoke(current_langgraph_state)
        end_time = time.perf_counter()
        execution_time_ms = (end_time - start_time) * 1000
        mem_usage_mb = process.memory_info().rss / (1024 * 1024) # in MB
        langgraph_memory_results.append({
            "iteration": current_langgraph_state['iteration'],
            "state_size": len(current_langgraph_state['data']),
            "memory_mb": mem_usage_mb,
            "execution_time_ms": execution_time_ms
        })
    print(json.dumps({"langgraph_memory_benchmark": langgraph_memory_results}, indent=2))
