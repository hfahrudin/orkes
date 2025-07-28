from agents.core import AgentInterface
from typing import Callable, Union, Dict, Optional
from orkes.graph.utils import function_assertion, is_typeddict_class, check_dict_values_type
from orkes.graph.unit import Node, Edge, ForwardEdge, ConditionalEdge, _StartNode, _EndNode
from orkes.graph.schema import NodePoolItem


START = _StartNode()
END = _EndNode()


class OrkesGraph:
    def __init__(self, state):
        self.nodes_pool: Dict[str, NodePoolItem] = {
            "START" : NodePoolItem(node=START),
            "END" : NodePoolItem(node=END)
        }
        if not is_typeddict_class(state):
            raise TypeError("Expected a TypedDict class")
        self.state = state
        self._freeze = False

    def add_node(self, name: str, func: Callable):
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")
    
        if name in self.nodes_pool:
            raise ValueError(f"Agent '{name}' already exists.")

        if not function_assertion(func, type(self.state)):
            raise TypeError(
                f"No parameter of 'node' has type matching Graph State ({type(self.state)})."
            )
        self.nodes_pool[name] = NodePoolItem(node=Node(name, func))


    def add_edge(self, from_node: Union[str, _StartNode], to_node: Union[str, _EndNode]) -> None:
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")

        from_node_item = self._validate_from_node(from_node)

        to_node_item = self._validate_to_node(to_node)

        edge = ForwardEdge(from_node_item, to_node_item)

        self.nodes_pool[from_node_item.node.name].edge = edge

    def add_conditional_edges(self, from_node: Union[str, _StartNode], gate_function: Callable, condition: Dict[str, Union[str, Node]]):
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")
        
        from_node_item = self._validate_from_node(from_node)

        if not function_assertion(gate_function, type(self.state)):
            raise TypeError(
                f"No parameter of 'gate_function' has type matching Graph State ({type(self.state)})."
            )

        self._validate_condition(condition)

        edge = ConditionalEdge(from_node_item, gate_function, condition)

        self.nodes_pool[from_node_item.node.name].edge = edge

    def _validate_condition(self, condition: Dict[str, Union[str, Node]]):
        for key, target in condition.items():
            #if target is a string, it must be a registered node
            if isinstance(target, str):
                if target not in self.nodes_pool:
                    raise ValueError(
                        f"Condition branch '{key}' points to node '{target}', "
                        f"but that node does not exist in the workflow."
                    )
            # if it's END or a Node object, allow it
            elif isinstance(target, Node):
                raise TypeError(
                    f"Condition branch '{key}' must map to a str (node name), "
                    f"a Node object, or END. Got {type(target).__name__}"
                )

    def _validate_from_node(self, from_node: Union[str, _StartNode]):
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")
        
        if not (isinstance(from_node, str) or from_node is START):
            raise TypeError(f"'from_node' must be str or START, got {type(from_node)}")

        if isinstance(from_node, str):
            if from_node not in self.nodes_pool:
                raise ValueError(f"From node '{from_node}' does not exist")
            from_node_item = self.nodes_pool[from_node]
        else:
            from_node_item = self.nodes_pool['START']

        if from_node_item.edge is not None:
            raise RuntimeError("Edge already assigned to this node.")
        
        return from_node_item
    
    def _validate_to_node(self, to_node: Union[str, _EndNode]):
        if not (isinstance(to_node, str) or to_node is END):
            raise TypeError(f"'to_node' must be str or END, got {type(to_node)}")

        if isinstance(to_node, str):
            if to_node not in self.nodes_pool:
                raise ValueError(f"To node '{to_node}' does not exist")
            to_node_item = self.nodes_pool[to_node]
        else:
            to_node_item = self.nodes_pool['END']
        return to_node_item

    def run(self, query):
        if not self._freeze:
            raise RuntimeError("Can only run after compile")

        pass

    def compile(self):
        #check nodes need to have branch
        #check start point inttegrity
        #check all conditional
        #checkk all fallback
        #check end point integrity
        #check all function
        #should have all exit node
        #no loose end
        pass
    

# function example
# "function with state argument + agent is the agreed node"
# # Test classes
# class MyState:
#     pass

# # Test functions
# def generate_file(state: MyState, x: int):
#     pass


#Graph feature:
# DAG, able to cycle, sequential, conditional. 
#Runner functions: TODO: gambar graph
#Notes:

# # Graph state
# class State(TypedDict):
#     topic: str
#     joke: str
#     improved_joke: str
#     final_joke: str