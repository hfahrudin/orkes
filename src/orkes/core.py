from agents.core import AgentInterface
from typing import Callable
from orkes.utils import function_assertion
import networkx as nx

# Sentinel constants
START = "__start__"
END = "__end__"


class Orkes:
    def __init__(self, state):
        self.node_pools = {}
        self.state = state
        self.graphs = nx.DiGraph()
        self._freeze = False


    def add_node(self, name: str, node: Callable):
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")
        if name in self.node_pools:
            raise ValueError(f"Agent '{name}' already exists.")

        assert function_assertion(node, type(self.state)), (
            f"No parameter of 'node' has type matching self.state ({type(self.state)})."
        )
        self.graphs.add_node(name, func=node)

    def add_edge(self, from_node, to_node):
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")
        self.graphs.add_edge(from_node, to_node)

    def add_conditional_edges(self, from_node, judge_node, outcome_to_node):
        pass

    def run(self, query):
        for node in nx.topological_sort(self.graphs):
            func = self.graphs.nodes[node].get("func")
            if func:
                func(query)
            

        pass

    def compile(self):
        pass

# function example
# "function with state argument + agent is the agreed node"
# # Test classes
# class MyState:
#     pass

# # Test functions
# def generate_file(state: MyState, x: int):
#     pass


# TODO:
# "belajar langchain/graph memory management"
# "Orkes need accept state as memory management"
# "fallback limitation avoiding unlimited loop"
# "DAG based graph"
# "sentinel object, allow multiple end and start -> need to have assertion"
