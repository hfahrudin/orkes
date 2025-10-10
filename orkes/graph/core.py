from orkes.agents.core import AgentInterface
from typing import Callable, Union, Dict, Optional, List
from orkes.graph.utils import function_assertion, is_typeddict_class, check_dict_values_type
from orkes.graph.unit import Node, Edge, ForwardEdge, ConditionalEdge, _StartNode, _EndNode
from orkes.graph.schema import NodePoolItem
from orkes.graph.runner import GraphRunner


class OrkesGraph:
    def __init__(self, state):
        self.state = state
        self.START = _StartNode(self.state)
        self.END = _EndNode(self.state)
        self._nodes_pool: Dict[str, NodePoolItem] = {
            "START" : NodePoolItem(node=self.START),
            "END" : NodePoolItem(node=self.END)
        }
        self._edges_pool: List[Edge] = []
        if not is_typeddict_class(state):
            raise TypeError("Expected a TypedDict class")
        self.state = state
        self._freeze = False

    def add_node(self, name: str, func: Callable):
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")
    
        if name in self._nodes_pool:
            raise ValueError(f"Agent '{name}' already exists.")

        if not function_assertion(func, self.state):
            raise TypeError(
                f"No parameter of 'node' has type matching Graph State ({self.state})."
            )
        self._nodes_pool[name] = NodePoolItem(node=Node(name, func, self.state))


    def add_edge(self, from_node: Union[str, _StartNode], to_node: Union[str, _EndNode], max_passes: int = 25) -> None:
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")

        from_node_item = self._validate_from_node(from_node)

        to_node_item = self._validate_to_node(to_node)

        edge = ForwardEdge(from_node_item, to_node_item, max_passes=max_passes)

        self._nodes_pool[from_node_item.node.name].edge = edge
        self._edges_pool.append(edge)
        if to_node_item == self._nodes_pool['END']:
            #TODO: need to have safer end handler
            to_node_item.edge = "<END GRAPH TOKEN>"


    def add_conditional_edge(self, from_node: Union[str, _StartNode], gate_function: Callable, condition: Dict[str, str], max_passes: int = 25):
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")
        
        from_node_item = self._validate_from_node(from_node)

        if not function_assertion(gate_function, self.state):
            raise TypeError(
                f"No parameter of 'gate_function' has type matching Graph State ({self.state})."
            )

        self._validate_condition(condition)

        edge = ConditionalEdge(from_node_item, gate_function, condition, max_passes=max_passes)
        self._edges_pool.append(edge)
        self._nodes_pool[from_node_item.node.name].edge = edge

    def _validate_condition(self, condition: Dict[str, Union[str, Node]]):
        for key, target in condition.items():
            #if target is a string, it must be a registered node
            if isinstance(target, str):
                if target not in self._nodes_pool:
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
        
        if not (isinstance(from_node, str) or from_node is self.START ):
            raise TypeError(f"'from_node' must be str or START, got {type(from_node)}")

        #TODO : node need to return graph (?)
        
        if isinstance(from_node, str):
            if from_node not in self._nodes_pool:
                raise ValueError(f"From node '{from_node}' does not exist")
            from_node_item = self._nodes_pool[from_node]
        else:
            from_node_item = self._nodes_pool['START']

        if from_node_item.edge is not None:
            raise RuntimeError("Edge already assigned to this node.")
        
        return from_node_item
    
    def _validate_to_node(self, to_node: Union[str, _EndNode]):
        if not (isinstance(to_node, str) or to_node is self.END ):
            raise TypeError(f"'to_node' must be str or END, got {type(to_node)}")

        if isinstance(to_node, str):
            if to_node not in self._nodes_pool:
                raise ValueError(f"To node '{to_node}' does not exist")
            to_node_item = self._nodes_pool[to_node]
        else:
            to_node_item = self._nodes_pool['END']
        return to_node_item

    def compile(self):
        #check start point inttegrity
        if not self._nodes_pool['START'].edge:
            raise RuntimeError("The Graph entry point is not assigned")

        #TODO: check all conditional
        #TODO: checkk all fallback

        #check end point integrity
        if not self._nodes_pool['END'].edge:
            raise RuntimeError("The Graph end point is not assigned")
        
        #should have all exit node
        for edge in self._edges_pool:
            if edge.edge_type == "__forward__":
                if not edge.to_node:
                    raise RuntimeError(f"Edge {edge.id} do not have node destination")
            #TODO: Conditional check
            elif edge.edge_type == "__conditional__":
                pass
        for node_name, node in self._nodes_pool.items():
            if not node.edge:  # Checks if edge is empty
                raise RuntimeError(f"Node '{node_name}' has an empty edge.")
        self._freeze = True
        
        return GraphRunner(nodes_pool=self._nodes_pool, graph_type=self.state)
    
    def detect_loop(self):
        start_pool = self._nodes_pool['START']
        visited_path = set()
        return self._walk_graph(start_pool, visited_path)

    def _walk_graph(self, current_node_item: NodePoolItem, path: set):
        current_node = current_node_item.node
        current_node_name = current_node.name
        # Loop check
        if current_node_name in path:
            return True  # Loop found

        path.add(current_node_name)

        next_node_item = current_node_item.edge.to_node
        if not isinstance(next_node_item.node, _EndNode):
            if self._walk_graph(next_node_item, path):
                return True

        path.remove(current_node_name)
        return False