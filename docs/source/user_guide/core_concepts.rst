.. _core_concepts:

==============
Core Concepts
==============

This section introduces the fundamental building blocks of Orkes. Understanding these concepts is key to using the library effectively.

.. mermaid::

   sequenceDiagram
       participant OrkesGraph
       participant State
       participant Node
       OrkesGraph->State: Initializes with
       State->Node: Passed to
       Node->State: Modifies

   A high-level overview of Orkes's core concepts.

1. The OrkesGraph
------------------
The ``OrkesGraph`` is the main canvas for your workflow. It holds the nodes and edges that define your application's logic. You initialize it with a state schema, which acts as the "memory" for your graph.

.. code-block:: python

    from orkes.graph.core import OrkesGraph
    from typing import TypedDict

    # Define the state (see below)
    class MyState(TypedDict):
        input: str
        output: str

    # Initialize the graph
    graph = OrkesGraph(MyState)


2. The State
------------
The state is a Python ``TypedDict`` that you define. It represents the data that flows through your graph. Each node receives the current state and can modify it, and these changes are passed to the next node in the execution path.

.. code-block:: python

    from typing import TypedDict, List

    class SearchState(TypedDict):
        user_query: str
        search_queries: List[str]
        current_index: int
        raw_results: List[str]
        is_finished: bool
        final_answer: str

3. Nodes
--------
Nodes are the building blocks of your graph. They are created from simple Python functions that take the current state as their only argument and return the modified state.

You add a node to the graph using the ``add_node`` method.

.. code-block:: python

    # A simple function to be used as a node
    def my_node_function(state: MyState) -> MyState:
        state['output'] = f"Processed: {state['input']}"
        return state

    # Add the node to the graph with a unique name
    graph.add_node('my_node', my_node_function)


4. Edges
--------
Edges connect your nodes to define the control flow. There are two types of edges:

- **Forward Edges**: These are simple, unconditional connections. You use ``add_edge`` to connect one node to another. The special ``graph.START`` and ``graph.END`` nodes represent the entry and exit points of the graph.

.. code-block:: python

    # Connect the start of the graph to 'my_node'
    graph.add_edge(graph.START, 'my_node')

    # Connect 'my_node' to the end of the graph
    graph.add_edge('my_node', graph.END)

- **Conditional Edges**: These allow for branching logic. You use ``add_conditional_edge`` to route the execution to different nodes based on the output of a "gate function". This is covered in more detail in the "Advanced Control Flow" guide.
