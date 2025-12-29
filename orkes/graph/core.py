from typing import Callable, Union, Dict, List
from orkes.graph.utils import function_assertion, is_typeddict_class
from orkes.graph.unit import Node, Edge, ForwardEdge, ConditionalEdge, _StartNode, _EndNode
from orkes.graph.schema import NodePoolItem
from orkes.graph.runner import GraphRunner
import uuid

class OrkesGraph:
    """A class to represent a stateful graph for orchestrating multi-agent workflows.

    The OrkesGraph allows you to define a graph of nodes, where each node is a function
    that operates on a shared state. The graph can have a single start and end point,
    and nodes can be connected with forward or conditional edges.

    Attributes:
        state (type): The TypedDict class that defines the shared state of the graph.
        name (str): The name of the graph.
        description (str): A description of the graph.
        traced (bool): Whether to trace the graph execution.

    Example:
        >>> from typing import TypedDict, List
        >>>
        >>> class MyState(TypedDict):
        ...     messages: List[str]
        ...
        >>> def node1(state: MyState) -> MyState:
        ...     state['messages'].append("Hello from node1")
        ...     return state
        ...
        >>> def node2(state: MyState) -> MyState:
        ...     state['messages'].append("Hello from node2")
        ...     return state
        ...
        >>> graph = OrkesGraph(state=MyState)
        >>> graph.add_node("node1", node1)
        >>> graph.add_node("node2", node2)
        >>> graph.add_edge(graph.START, "node1")
        >>> graph.add_edge("node1", "node2")
        >>> graph.add_edge("node2", graph.END)
        >>> compiled_graph = graph.compile()
        >>> result = compiled_graph.run({"messages": []})
        >>> print(result)
        {'messages': ['Hello from node1', 'Hello from node2']}
    """

    def __init__(self, state, name: str = "default_graph", description: str = "", traced: bool = True):
        """Initializes an OrkesGraph.

        Args:
            state (type): The TypedDict class that defines the shared state of the graph.
            name (str, optional): The name of the graph. Defaults to "default_graph".
            description (str, optional): A description of the graph. Defaults to "".
            traced (bool, optional): Whether to trace the graph execution. Defaults to True.

        Raises:
            TypeError: If the state is not a TypedDict class.
        """
        self.state = state
        self.name = name
        self.traced = traced
        self.description = description
        self.id = "graph_" + str(uuid.uuid4())
        self.START = _StartNode(self.state)
        self.END = _EndNode(self.state)
        self._nodes_pool: Dict[str, NodePoolItem] = {
            "START": NodePoolItem(node=self.START),
            "END": NodePoolItem(node=self.END)
        }
        self._edges_pool: List[Edge] = []
        if not is_typeddict_class(state):
            raise TypeError("Expected a TypedDict class")
        self.state = state
        self._freeze = False

    def add_node(self, name: str, func: Callable):
        """Adds a node to the graph.

        Args:
            name (str): The name of the node. Must be unique.
            func (Callable): The function associated with the node. This function must
                         accept a parameter of the same type as the graph's state.

        Raises:
            RuntimeError: If the graph has been compiled.
            ValueError: If a node with the same name already exists.
            TypeError: If the function signature does not match the graph state.
        """
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
        """Adds a forward edge between two nodes.

        Args:
            from_node (Union[str, _StartNode]): The starting node of the edge.
            to_node (Union[str, _EndNode]): The ending node of the edge.
            max_passes (int, optional): The maximum number of times this edge can be
                                      traversed. Defaults to 25.

        Raises:
            RuntimeError: If the graph has been compiled.
        """
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")

        from_node_item = self._validate_from_node(from_node)
        to_node_item = self._validate_to_node(to_node)
        edge = ForwardEdge(from_node_item, to_node_item, max_passes=max_passes)
        self._nodes_pool[from_node_item.node.name].edge = edge
        self._edges_pool.append(edge)
        if to_node_item == self._nodes_pool['END']:
            # A special token to indicate that the graph has reached its end.
            to_node_item.edge = "<END GRAPH TOKEN>"

    def add_conditional_edge(self, from_node: Union[str, _StartNode], gate_function: Callable, condition: Dict[str, str], max_passes: int = 25):
        """Adds a conditional edge from a node.

        The `gate_function` determines which branch to take based on its return value.
        The `condition` dictionary maps the return values of the `gate_function` to
        the next node.

        Args:
            from_node (Union[str, _StartNode]): The starting node of the edge.
            gate_function (Callable): A function that returns a string indicating which
                                    branch to take.
            condition (Dict[str, str]): A dictionary mapping the return values of the
                                      `gate_function` to the next node.
            max_passes (int, optional): The maximum number of times this edge can be
                                      traversed. Defaults to 25.

        Raises:
            RuntimeError: If the graph has been compiled.
            TypeError: If the gate_function's signature does not match the graph state.
        """
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
        if "END" in condition.values():
            self._nodes_pool["END"].edge = "<END GRAPH TOKEN>"

    def _validate_condition(self, condition: Dict[str, Union[str, Node]]):
        """Validates the condition dictionary for a conditional edge.

        Args:
            condition (Dict[str, Union[str, Node]]): The condition dictionary.

        Raises:
            ValueError: If a condition branch points to a non-existent node.
            TypeError: If a condition branch maps to an invalid type.
        """
        for key, target in condition.items():
            # If the target is a string, it must be a registered node.
            if isinstance(target, str):
                if target not in self._nodes_pool:
                    raise ValueError(
                        f"Condition branch '{key}' points to node '{target}', "
                        f"but that node does not exist in the workflow."
                    )
            # If it's END or a Node object, it's not allowed.
            elif isinstance(target, Node):
                raise TypeError(
                    f"Condition branch '{key}' must map to a str (node name), "
                    f"a Node object, or END. Got {type(target).__name__}"
                )

    def _validate_from_node(self, from_node: Union[str, _StartNode]):
        """Validates the 'from_node' of an edge.

        Args:
            from_node (Union[str, _StartNode]): The starting node of the edge.

        Returns:
            NodePoolItem: The node pool item for the 'from_node'.

        Raises:
            RuntimeError: If the graph has been compiled or if the edge is already assigned.
            TypeError: If 'from_node' is not a string or the START node.
            ValueError: If 'from_node' does not exist.
        """
        if self._freeze:
            raise RuntimeError("Cannot modify after compile")

        if not (isinstance(from_node, str) or from_node is self.START):
            raise TypeError(f"'from_node' must be str or START, got {type(from_node)}")

        # TODO: The node should return the graph.

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
        """Validates the 'to_node' of an edge.

        Args:
            to_node (Union[str, _EndNode]): The ending node of the edge.

        Returns:
            NodePoolItem: The node pool item for the 'to_node'.

        Raises:
            TypeError: If 'to_node' is not a string or the END node.
            ValueError: If 'to_node' does not exist.
        """
        if not (isinstance(to_node, str) or to_node is self.END):
            raise TypeError(f"'to_node' must be str or END, got {type(to_node)}")

        if isinstance(to_node, str):
            if to_node not in self._nodes_pool:
                raise ValueError(f"To node '{to_node}' does not exist")
            to_node_item = self._nodes_pool[to_node]
        else:
            to_node_item = self._nodes_pool['END']
        return to_node_item

    def compile(self):
        """Compiles the graph, making it ready for execution.

        This method checks the integrity of the graph, ensuring that all nodes have
        edges and that the start and end points are properly configured. Once compiled,
        the graph becomes immutable.

        Returns:
            GraphRunner: An object that can run the compiled graph.

        Raises:
            RuntimeError: If the graph entry or end point is not assigned, or if a node has an empty edge.
        """
        # Check if the start point is connected.
        if not self._nodes_pool['START'].edge:
            raise RuntimeError("The Graph entry point is not assigned")

        # Check if the end point is connected.
        if not self._nodes_pool['END'].edge:
            raise RuntimeError("The Graph end point is not assigned")

        # Ensure all edges have a destination.
        for edge in self._edges_pool:
            if edge.edge_type == "__forward__":
                if not edge.to_node:
                    raise RuntimeError(f"Edge {edge.id} do not have node destination")
            # TODO: Add checks for conditional edges.
            elif edge.edge_type == "__conditional__":
                pass
        for node_name, node in self._nodes_pool.items():
            if not node.edge:  # Checks if edge is empty
                raise RuntimeError(f"Node '{node_name}' has an empty edge.")
        self._freeze = True

        return GraphRunner(graph_name=self.name,
                           graph_description=self.description,
                           nodes_pool=self._nodes_pool,
                           graph_type=self.state,
                           traced=self.traced)

    def detect_loop(self):
        """Detects loops in the graph.

        Returns:
            bool: True if a loop is detected, False otherwise.
        """
        start_pool = self._nodes_pool['START']
        visited_path = set()
        return self._walk_graph(start_pool, visited_path)

    def _walk_graph(self, current_node_item: NodePoolItem, path: set) -> bool:
        """Recursively walks the graph to detect loops.

        Args:
            current_node_item (NodePoolItem): The current node to visit.
            path (set): A set of visited node names in the current path.

        Returns:
            bool: True if a loop is detected, False otherwise.
        """
        current_node = current_node_item.node
        current_node_name = current_node.name
        # If the current node is already in the path, a loop is found.
        if current_node_name in path:
            return True  # Loop found

        path.add(current_node_name)

        next_node_item = current_node_item.edge.to_node
        if not isinstance(next_node_item.node, _EndNode):
            if self._walk_graph(next_node_item, path):
                return True

        path.remove(current_node_name)
        return False
