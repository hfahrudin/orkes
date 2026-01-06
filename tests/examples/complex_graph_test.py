from orkes.graph.core import OrkesGraph
from typing import TypedDict, List
import random

# Define the state structure
class ComplexState(TypedDict):
    main_counter: int
    branch_a_counter: int
    branch_b_counter: int
    branch_a_sub_branch_counters: List[int]
    branch_b_sub_branch_counters: List[int]
    branch_a_loop_exit: bool
    branch_b_loop_exit: bool


def main_split_node(state: ComplexState) -> ComplexState:
    print("Main split node")
    return state

def branch_a_start(state: ComplexState) -> ComplexState:
    print("Branch A start")
    state['branch_a_counter'] = 0
    state['branch_a_loop_exit'] = False
    return state

def branch_b_start(state: ComplexState) -> ComplexState:
    print("Branch B start")
    state['branch_b_counter'] = 0
    state['branch_b_loop_exit'] = False
    return state

def loop_a_node(state: ComplexState) -> ComplexState:
    state['branch_a_counter'] += 1
    print(f"Loop A iteration: {state['branch_a_counter']}")
    if state['branch_a_counter'] >= 2:
        state['branch_a_loop_exit'] = True
    return state
    
def loop_a_gate(state: ComplexState) -> str:
    if state['branch_a_loop_exit']:
        return 'exit'
    else:
        return 'continue'

def branch_a_split_node(state: ComplexState) -> ComplexState:
    print("Branch A split node")
    state['branch_a_sub_branch_counters'] = [0, 0]
    return state

def sub_branch_a1(state: ComplexState) -> ComplexState:
    print("Sub-branch A1")
    state['branch_a_sub_branch_counters'][0] += 1
    return state

def sub_branch_a2(state: ComplexState) -> ComplexState:
    print("Sub-branch A2")
    state['branch_a_sub_branch_counters'][1] += 1
    return state

def branch_a_aggregator(state: ComplexState) -> ComplexState:
    print("Branch A aggregator")
    return state

def loop_b_node(state: ComplexState) -> ComplexState:
    state['branch_b_counter'] += 1
    print(f"Loop B iteration: {state['branch_b_counter']}")
    if state['branch_b_counter'] >= 3:
        state['branch_b_loop_exit'] = True
    return state

def loop_b_gate(state: ComplexState) -> str:
    if state['branch_b_loop_exit']:
        return 'exit'
    else:
        return 'continue'

def branch_b_split_node(state: ComplexState) -> ComplexState:
    print("Branch B split node")
    state['branch_b_sub_branch_counters'] = [0, 0]
    return state

def sub_branch_b1(state: ComplexState) -> ComplexState:
    print("Sub-branch B1")
    state['branch_b_sub_branch_counters'][0] += 1
    return state

def sub_branch_b2(state: ComplexState) -> ComplexState:
    print("Sub-branch B2")
    state['branch_b_sub_branch_counters'][1] += 1
    return state

def branch_b_aggregator(state: ComplexState) -> ComplexState:
    print("Branch B aggregator")
    return state

def main_aggregator(state: ComplexState) -> ComplexState:
    print("Main aggregator")
    return state


# --- Initialize Graph ---
complex_graph = OrkesGraph(ComplexState)
START_node = complex_graph.START
END_node = complex_graph.END

# Add nodes
complex_graph.add_node('main_split', main_split_node)
complex_graph.add_node('branch_a_start', branch_a_start)
complex_graph.add_node('branch_b_start', branch_b_start)
complex_graph.add_node('loop_a', loop_a_node)
complex_graph.add_node('branch_a_split', branch_a_split_node)
complex_graph.add_node('sub_branch_a1', sub_branch_a1)
complex_graph.add_node('sub_branch_a2', sub_branch_a2)
complex_graph.add_node('branch_a_aggregator', branch_a_aggregator)
complex_graph.add_node('loop_b', loop_b_node)
complex_graph.add_node('branch_b_split', branch_b_split_node)
complex_graph.add_node('sub_branch_b1', sub_branch_b1)
complex_graph.add_node('sub_branch_b2', sub_branch_b2)
complex_graph.add_node('branch_b_aggregator', branch_b_aggregator)
complex_graph.add_node('main_aggregator', main_aggregator)


# Add edges

# Define Branch A internal structure first, leading to main_aggregator
complex_graph.add_edge('branch_a_start', 'loop_a')
complex_graph.add_conditional_edge('loop_a', loop_a_gate, {'exit': 'branch_a_split', 'continue': 'loop_a'})
complex_graph.add_edge('sub_branch_a1', 'branch_a_aggregator')
complex_graph.add_edge('sub_branch_a2', 'branch_a_aggregator')
complex_graph.add_parallel_edges('branch_a_split', ['sub_branch_a1', 'sub_branch_a2'], 'branch_a_aggregator')
complex_graph.add_edge('branch_a_aggregator', 'main_aggregator')


# Define Branch B internal structure, leading to main_aggregator
complex_graph.add_edge('branch_b_start', 'loop_b')
complex_graph.add_conditional_edge('loop_b', loop_b_gate, {'exit': 'branch_b_split', 'continue': 'loop_b'})
complex_graph.add_edge('sub_branch_b1', 'branch_b_aggregator')
complex_graph.add_edge('sub_branch_b2', 'branch_b_aggregator')
complex_graph.add_parallel_edges('branch_b_split', ['sub_branch_b1', 'sub_branch_b2'], 'branch_b_aggregator')
complex_graph.add_edge('branch_b_aggregator', 'main_aggregator')

# Now add the main parallel branches
complex_graph.add_edge(START_node, 'main_split')
complex_graph.add_parallel_edges('main_split', ['branch_a_start', 'branch_b_start'], 'main_aggregator')

complex_graph.add_edge('main_aggregator', END_node)


# Compile the graph
runner = complex_graph.compile()

# --- Run Test ---
initial_state: ComplexState = {
    "main_counter": 0,
    "branch_a_counter": 0,
    "branch_b_counter": 0,
    "branch_a_sub_branch_counters": [],
    "branch_b_sub_branch_counters": [],
    "branch_a_loop_exit": False,
    "branch_b_loop_exit": False
}

result = runner.run(initial_state)

runner.visualize_trace()

print("Final State:")
print(result)
