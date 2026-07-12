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

You create a conditional edge using the ``add_conditional_edge`` method. This method takes:
- The name of the source node.
- The gate function.
- A dictionary that maps the possible return values of the gate function to the names of the destination nodes.
- (Optional) ``max_passes``, capping how many times this edge can be traversed (see the Looping section below).

There is no fallback/default destination -- if the gate function returns a value that isn't a key in the dictionary, Orkes raises a ``KeyError`` naming the node, the unexpected value, and the valid options, so make sure every possible return value of your gate function has a matching entry.


.. mermaid::

    graph TD
        subgraph Conditional Edge
            A[set_number] --> B{is_even_or_odd};
            B -- "returns 'even'" --> C[process_even];
            B -- "returns 'odd'" --> D[process_odd];
        end

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
You can create loops by routing a conditional edge back to a previous node in the graph. Orkes has a built-in mechanism to prevent infinite loops: every ``add_edge``, ``add_conditional_edge``, and ``add_parallel_edges`` call accepts a ``max_passes`` argument (defaulting to ``25``) that caps how many times that specific edge can be traversed before Orkes raises a ``RuntimeError``.

.. mermaid::

    graph TD
        subgraph Looping
            A[increment_node] --> B{counter_gate};
            B -- "returns 'continue'" --> A;
            B -- "returns 'finish'" --> C[END];
        end

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
        },
        max_passes=100  # allow up to 100 loop iterations on this edge (default is 25)
    )

4. Parallel Execution
---------------------
Orkes supports branching a graph into multiple independent paths, a pattern also known as a **fan-out/fan-in** strategy.

- **Fan-Out**: The graph "fans out" from a single node into multiple branches. Each branch runs against its own isolated copy of the state, so branches never see each other's writes -- but branches currently execute one after another rather than truly concurrently.
- **Fan-In**: The branches "fan in" to a single aggregation node, which runs exactly once after every branch has completed, with each branch's changes merged into the shared state. The main execution path only continues from there.

.. mermaid::

    graph TD
        subgraph Fan-Out
            A(start_node) --> B(branch_1);
            A --> C(branch_2);
            A --> E(...);
        end
        subgraph Fan-In
            B --> D[aggregation_node];
            C --> D;
            E --> D;
        end

You can implement this using the `add_parallel_edges` method, which splits the execution into multiple paths. All parallel branches must eventually converge into a single `aggregation_node`.

.. code-block:: python

    from orkes.graph.core import OrkesGraph
    from typing import TypedDict

    class ParallelState(TypedDict):
        branch_1_visited: bool
        branch_2_visited: bool

    def branch_1_node(state: ParallelState) -> ParallelState:
        state['branch_1_visited'] = True
        return state

    def branch_2_node(state: ParallelState) -> ParallelState:
        state['branch_2_visited'] = True
        return state

    def aggregation_node(state: ParallelState) -> ParallelState:
        # This node will only be reached after both branches complete
        assert state['branch_1_visited']
        assert state['branch_2_visited']
        return state

    graph = OrkesGraph(ParallelState)

    graph.add_node('branch_1', branch_1_node)
    graph.add_node('branch_2', branch_2_node)
    graph.add_node('aggregator', aggregation_node)

    graph.add_parallel_edges(
        graph.START,
        to_nodes=['branch_1', 'branch_2'],
        aggregation_node='aggregator'
    )

    # Edges from parallel branches to the aggregation node
    graph.add_edge('branch_1', 'aggregator')
    graph.add_edge('branch_2', 'aggregator')

    # Edge from the aggregation node to the end
    graph.add_edge('aggregator', graph.END)
