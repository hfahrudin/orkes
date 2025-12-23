from orkes.graph.core import OrkesGraph
from typing import TypedDict
import random
# Define the state structure
class State(TypedDict):
    initial: int
    add_result: int
    multiply_result: int
    condition_result: bool

def add_3(state: State):
    """
    Initializes the workflow by adding 3 to the starting input.
    - Input: state['initial']
    - Output: Updates state['add_result']
    """
    result = state.get('initial', 0) + 3
    state['add_result'] = result
    return state

def multiply_by_2(state: State):
    """
    Core processing node. Generates a random number and scales it.
    This node acts as the loop entry point if the condition fails.
    - Logic: (Random 1-10) * 2
    - Output: Updates state['multiply_result']
    """
    rand_value = random.randint(1,7)
    result = rand_value * 2
    state['multiply_result'] = result
    return state

def greater_than_10(state: State):
    """
    Evaluator node that checks if the current result meets the threshold.
    - Logic: multiply_result > 10
    - Output: Sets state['condition_result'] (bool)
    """
    value = state.get('multiply_result', 0)
    result = value > 10
    state['condition_result'] = result
    return state

def path_true_node(state: State):
    """
    Success terminal path. Executes when the condition is met.
    - Flow: Transitions to END_node.
    """
    print("Condition was True!")
    return state

def path_false_node(state: State):
    """
    Failure/Retry path. Executes when the condition is not met.
    - Flow: Loops back to multiply_by_2.
    """
    print("Condition was False!")
    return state

def conditional_node(state: State):
    """
    The router/edge logic. 
    Determines the next node based on the boolean result in the state.
    - Returns: 'true' (path_true) or 'false' (path_false)
    """
    if state.get('condition_result', False):
        return 'true'
    else:
        return 'false'

# --- Initialize Graph ---
agent_graph = OrkesGraph(State)
START_node = agent_graph.START
END_node = agent_graph.END

# Add nodes
agent_graph.add_node('add_3', add_3)
agent_graph.add_node('multiply_by_2', multiply_by_2)
agent_graph.add_node('greater_than_10', greater_than_10)
agent_graph.add_node('path_true', path_true_node)
agent_graph.add_node('path_false', path_false_node)

# Add edges
agent_graph.add_edge(START_node, 'add_3')
agent_graph.add_edge('add_3', 'multiply_by_2')
agent_graph.add_edge('multiply_by_2', 'greater_than_10')
agent_graph.add_conditional_edge('greater_than_10', conditional_node, {'true' : 'path_true', 'false' : 'path_false'})

agent_graph.add_edge('path_false', 'multiply_by_2')
agent_graph.add_edge('path_true', END_node)

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

# print(agent_graph._nodes_pool)
