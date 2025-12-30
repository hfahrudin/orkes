.. _advanced_control_flow:

=======================
Advanced Control Flow
=======================

This guide explains how to use conditional edges to create branching logic in your Orkes graphs. This is a powerful feature that allows you to build complex, agent-like behaviors.

1. The Gate Function
--------------------
Conditional edges work by using a "gate function". This is a simple Python function that takes the current state and returns a string. The string returned by the gate function determines which path the graph execution will take.

.. code-block:: python

    from typing import TypedDict

    class NumberState(TypedDict):
        number: int

    def is_even_or_odd(state: NumberState) -> str:
        if state['number'] % 2 == 0:
            return 'even'
        else:
            return 'odd'

2. The Conditional Edge
-----------------------

.. mermaid::

   graph TD
       A[Source Node] --> B{Gate Function};
       B -- "Returns 'Path A'" --> C[Destination Node A];
       B -- "Returns 'Path B'" --> D[Destination Node B];
       style A fill:#f9f,stroke:#333,stroke-width:2px;
       style B fill:#bbf,stroke:#333,stroke-width:2px;
       style C fill:#ccf,stroke:#333,stroke-width:2px;
       style D fill:#ccf,stroke:#333,stroke-width:2px;

   A conditional edge allows the graph to branch based on the state.

You create a conditional edge using the ``add_conditional_edge`` method. This method takes four arguments:
- The name of the source node.
- The gate function.
- A dictionary that maps the possible return values of the gate function to the names of the destination nodes.
- (Optional) A default destination node, if none of the keys in the dictionary match the return value of the gate function.

.. code-block:: python

    from orkes.graph.core import OrkesGraph
    # ... (NumberState and is_even_or_odd definition)

    graph = OrkesGraph(NumberState)

    # Assume 'process_even' and 'process_odd' are nodes you have already defined
    # graph.add_node('process_even', process_even_node)
    # graph.add_node('process_odd', process_odd_node)

    # Add a node that sets the number
    def set_number_node(state: NumberState) -> NumberState:
        state['number'] = 10
        return state
    graph.add_node('set_number', set_number_node)


    # Add the conditional edge
    graph.add_conditional_edge(
        'set_number',
        is_even_or_odd,
        {
            'even': 'process_even',
            'odd': 'process_odd'
        }
    )

3. Looping
----------
You can create loops by routing a conditional edge back to a previous node in the graph. Orkes has a built-in mechanism to prevent infinite loops. The ``GraphRunner`` has a ``max_passes`` parameter (defaulting to 10) that will stop the execution if the graph runs for too many steps.

.. code-block:: python

    # Example of a loop
    # ... (graph and other nodes)

    def counter_gate(state: CounterState) -> str:
        if state['count'] < 5:
            return 'continue'
        else:
            return 'finish'

    graph.add_conditional_edge(
        'increment_node',
        counter_gate,
        {
            'continue': 'increment_node', # Edge back to the same node
            'finish': graph.END
        }
    )
