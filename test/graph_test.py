
import sys
import os

# Get the absolute path of folder A and add it to sys.path
sys.path.insert(0, os.path.abspath('../')) 

from orkes.graph.core import OrkesGraph
from orkes.graph.unit import Node
from typing import TypedDict

class State(TypedDict):
    topic: str
    joke: str
    improved_joke: str
    final_joke: str


def multiply_by_2(state: State):
    result = 1 * 2
    state['multiply_result'] = result  # save intermediate result
    return result

def add_3(state: State):
    result = 2 + 3
    state['add_result'] = result
    return result

def greater_than_10(state: State):
    result = 3 > 10
    state['condition_result'] = result
    return result

# Initialize graph state as an empty dict
agent_graph = OrkesGraph(State)
END_node = agent_graph.END
START_node = agent_graph.START
agent_graph.add_node('multiply_by_2' , multiply_by_2)
agent_graph.add_node('add_3' , add_3)
agent_graph.add_node('greater_than_10' , greater_than_10)

agent_graph.add_edge("add_3", "multiply_by_2")
agent_graph.add_edge("multiply_by_2", "greater_than_10")

agent_graph.add_edge(START_node, "add_3")
agent_graph.add_edge("greater_than_10", END_node)
# agent_graph.set_entry_point("multiply_by_2")
# agent_graph.set_end_point("greater_than_10")

agent_graph.compile()


print(agent_graph._nodes_pool)