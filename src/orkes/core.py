from agents.core import AgentInterface
from typing import Callable
from orkes.utils import function_assertion

# Sentinel constants
START = "__start__"
END = "__end__"


class Orkes:
    def __init__(self, state):
        self.node_pools = {}
        self.state = state


    def add_node(self, name: str, node: Callable):
        if name in self.node_pools:
            raise ValueError(f"Agent '{name}' already exists.")

        assert function_assertion(node, type(self.state)), (
            f"No parameter of 'node' has type matching self.state ({type(self.state)})."
        )
        self.node_pools[name] = node

    def add_edge(self, from_node, to_node):
        pass
    

# function example
# "function with state argument + agent is the agreed node"
# # Test classes
# class MyState:
#     pass

# # Test functions
# def generate_file(state: MyState, x: int):
#     pass


"belajar langchain/graph memory management"
"Orkes need accept state as memory management"
