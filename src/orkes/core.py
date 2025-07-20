from agents.core import AgentInterface
from typing import Callable
from orkes.utils import function_assertion, is_typeddict_class, check_dict_values_type
from orkes.unit import Node, ForwardEdge, ConditionalEdge
from typing import Dict, Any


# Sentinel constants
START = "__start__"
END = "__end__"

class Orkes:
    def __init__(self, state):
        self.node_pools: Dict[str, Node] = {}
        self.edge_pools: Dict[str, Any] = {}
        assert is_typeddict_class(state), "Expected a TypedDict class"
        self.state = state
        self._freeze = False

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

        edge = ForwardEdge(from_node, to_node)

        self.edge_pools[edge.id] = edge



    def add_conditional_edges(self, from_node_name: str, judge_func: Callable, condition: Dict):
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")
        
        assert from_node_name in self.node_pools, f"From node '{from_node_name}' does not exist"
        from_node: Node = self.node_pools[from_node_name]


        assert function_assertion(judge_func, type(self.state)), (
            f"No parameter of 'judge funciton' has type matching of Graph State({type(self.state)})."
        )

        assert check_dict_values_type(condition, Node), "Not all values in condition are Node instances"

        edge = ConditionalEdge(from_node, judge_func, condition)

        self.edge_pools[edge.id] = edge

    def run(self, query):
        if not self._freeze:
            raise RuntimeError("Can only run after compile")
        #TODO: Running Logic, How to map runtime, prolly using asyncio
        pass

    def compile(self):
        #check nodes need to have branch
        #check start point inttegrity
        #check all conditional
        #checkk all fallback
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


#Runner functions
# 1. identify all edges
# 2. encapsulate asyncio
# 3. allow multiple end 
# 4. allow multiple start
# 5. accept multiple from and multiple to
# basically any from to need to be list, so not necessarrly 1 to 1 but 1 to many can also
# - it should have start and END edge
# - belajar await
