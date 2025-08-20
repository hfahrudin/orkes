#FOR LOCAL TESTING
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from orkes.graph.core import OrkesGraph
from typing import TypedDict

# Define the state structure
class State(TypedDict):
    initial: int
    add_result: int
    multiply_result: int
    condition_result: bool

# Node functions
def add_3(state: State):
    result = state.get('initial', 0) + 3
    state['add_result'] = result
    return state

def multiply_by_2(state: State):
    value = state.get('add_result', 0)
    result = value * 2
    state['multiply_result'] = result
    return state

def greater_than_10(state: State):
    value = state.get('multiply_result', 0)
    result = value > 10
    state['condition_result'] = result
    return state

# --- Initialize Graph ---
agent_graph = OrkesGraph(State)
START_node = agent_graph.START
END_node = agent_graph.END

# Add nodes
agent_graph.add_node('add_3', add_3)
agent_graph.add_node('multiply_by_2', multiply_by_2)
agent_graph.add_node('greater_than_10', greater_than_10)

# Add edges
agent_graph.add_edge(START_node, 'add_3')
agent_graph.add_edge('add_3', 'multiply_by_2')
agent_graph.add_edge('multiply_by_2', 'greater_than_10')
agent_graph.add_edge('greater_than_10', END_node)

# Compile the graph
runner = agent_graph.compile()

# --- Run Test ---
state: State = {
    "initial": 3,
    "add_result": 0,
    "multiply_result": 0,
    "condition_result": False
}

result= runner.run(state)
print(result)
# print(agent_graph._nodes_pool)