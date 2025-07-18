
from typing import List, Dict
from typing import Callable

class Node:
    def __init__(self, name: str, func: Callable):
        """
        Initialize a Node.

        Parameters:
        - name (str): The unique identifier for the node.
        - name (func): The unique identifier for the node.
        """
        self.name: str = name
        self.func: str = func
        self.next: List["Node"] = []
        self.prev: List["Node"] = []
        self.conditional : Dict = None

    def add_next(self, node: "Node") -> None:
        if node not in self.next:
            self.next.append(node)
            node.prev.append(self)  # Ensure bidirectional connection

    def add_prev(self, node: "Node") -> None:
        if node not in self.prev:
            self.prev.append(node)
            node.next.append(self)  # Ensure bidirectional connection

    def __repr__(self) -> str:
        return f"Node({self.name})"
