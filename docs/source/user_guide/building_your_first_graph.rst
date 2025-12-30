.. _building_your_first_graph:

=========================
Building Your First Graph
=========================

This guide will walk you through creating a simple Orkes graph from scratch. We will build a workflow that takes a user's name and generates a greeting.

1. Define the State
-------------------
First, we define the ``GreetingState``, which will hold the data for our graph.

.. code-block:: python

    from typing import TypedDict

    class GreetingState(TypedDict):
        name: str
        greeting: str

2. Create the Graph and Nodes
-----------------------------
Next, we'll create an ``OrkesGraph`` instance and define a simple Python function to act as our node. This function will take the state, generate a greeting, and update the state.

.. code-block:: python

    from orkes.graph.core import OrkesGraph
    # ... (GreetingState definition)

    # Initialize the graph with our state
    graph = OrkesGraph(GreetingState)

    # Define the node function
    def greeter_node(state: GreetingState) -> GreetingState:
        state['greeting'] = f"Hello, {state['name']}!"
        return state

    # Add the node to the graph
    graph.add_node('greeter', greeter_node)

3. Connect the Nodes with Edges
-------------------------------
Now, we define the flow of execution using edges. We'll connect the start of the graph to our ``greeter`` node, and the ``greeter`` node to the end of the graph.

.. code-block:: python

    # ... (graph and node definition)

    graph.add_edge(graph.START, 'greeter')
    graph.add_edge('greeter', graph.END)


4. Compile and Run the Graph
----------------------------
Before we can run the graph, we need to compile it. Then we can create a ``GraphRunner`` and execute the graph with an initial state.

.. code-block:: python

    # ... (full graph definition)
    from orkes.graph.runner import GraphRunner

    # Compile the graph
    compiled_graph = graph.compile()

    # Create a runner and an initial state
    runner = GraphRunner(compiled_graph)
    initial_state = GreetingState(name="World", greeting="")

    # Run the graph
    final_state = runner.run(initial_state)

    print(f"Final state: {final_state}")
    # Expected output: Final state: {'name': 'World', 'greeting': 'Hello, World!'}

5. Visualize the Execution
--------------------------
After running the graph, you can generate an interactive trace to visualize the execution.

.. code-block:: python

    # ... (after runner.run)

    runner.visualize_trace("greeting_trace.html")
    print("Trace file 'greeting_trace.html' generated.")

This will create an HTML file that you can open in your browser to inspect the graph's execution and state changes.
