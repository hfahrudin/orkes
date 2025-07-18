from agents.core import AgentInterface
from typing import Callable
from orkes.utils import function_assertion, is_typeddict_class
from orkes.unit import Node
from typing import Dict, List


# Sentinel constants
START = "__start__"
END = "__end__"

class Orkes:
    def __init__(self, state):
        self.node_pools: Dict[str, Node] = {}
        assert is_typeddict_class(state), "Expected a TypedDict class"
        self.state = state
        self._freeze = False
        self.start_edge = []
        self.end_edge = []

    def add_node(self, name: str, func: Callable):
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")
        if name in self.node_pools:
            raise ValueError(f"Agent '{name}' already exists.")

        assert function_assertion(func, type(self.state)), (
            f"No parameter of 'node' has type matching of Graph State({type(self.state)})."
        )
        self.node_pools[name] = Node(name, func)


    def add_edge(self, from_node_name: str, to_node_name: str) -> None:
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")
        
        assert from_node_name in self.node_pools, f"From node '{from_node_name}' does not exist"
        from_node: Node = self.node_pools[from_node_name]

        assert to_node_name in self.node_pools, f"To node '{to_node_name}' does not exist"
        to_node: Node = self.node_pools[to_node_name]

        from_node.add_next(to_node)



    def add_conditional_edges(self, from_node_name, judge_func, to_node_name):
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")
        
        assert from_node_name in self.node_pools, f"From node '{from_node_name}' does not exist"
        from_node: Node = self.node_pools[from_node_name]

        assert to_node_name in self.node_pools, f"To node '{to_node_name}' does not exist"
        to_node: Node = self.node_pools[to_node_name]

        assert function_assertion(judge_func, type(self.state)), (
            f"No parameter of 'judge funciton' has type matching of Graph State({type(self.state)})."
        )
        pass

    def run(self, query):
        if not self._freeze:
            raise RuntimeError("Can only run after compile")
        pass

    def compile(self):
        #check nodes need to have branch
        #check start point inttegrity
        #check end point integrity
        #check all function
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
