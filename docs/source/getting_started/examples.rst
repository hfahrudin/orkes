.. _examples:

========
Examples
========

This section provides a simple example to illustrate the core workflow of building, running, and visualizing an Orkes graph.

We'll define a simple graph that plans search queries, executes them, and then synthesizes a final answer.

1. Define the State Schema
--------------------------
First, define the `SearchState` which represents the data flowing through your graph.

.. code-block:: python

    from typing import TypedDict, List

    class SearchState(TypedDict):
        user_query: str
        search_queries: List[str]
        current_index: int
        raw_results: List[str]
        is_finished: bool
        final_answer: str

2. Initialize the OrkesGraph
-----------------------------
Create an instance of `OrkesGraph`, passing your defined state.

.. code-block:: python

    from orkes.graph.core import OrkesGraph
    # ... (SearchState definition from above)

    graph = OrkesGraph(SearchState)

3. Define Nodes (Tasks)
-----------------------
Nodes are Python functions that take the current state, perform an operation, and return the updated state. Here, we'll briefly show the planner node.

.. code-block:: python

    # ... (imports and SearchState definition)

    # Example: A simplified planner node
    def planner_node(state: SearchState):
        state['search_queries'] = ["query1", "query2"] # Simulate LLM generation
        state['current_index'] = 0
        state['raw_results'] = []
        state['is_finished'] = False
        return state

    graph.add_node('planner', planner_node)

4. Define Edges (Flow Control)
------------------------------
Edges define the sequence of execution between nodes. This includes conditional edges for branching logic.

.. code-block:: python

    # ... (graph and planner_node definition)
    from orkes.graph.core import OrkesGraph

    # Assuming other nodes like 'search_step' and 'synthesizer' are defined
    # For a full example, refer to `tests/examples/graph_service_test.py`

    # Add a simple edge from the start to the planner
    graph.add_edge(graph.START, 'planner')

    # Example of a conditional edge for looping (simplified)
    def check_loop_condition(state: SearchState):
        return 'complete' if state.get('is_finished') else 'loop'

    # Assuming 'search_step' and 'synthesizer' nodes are defined
    # graph.add_node('search_step', execute_search_node)
    # graph.add_node('synthesizer', synthesis_node)
    # graph.add_node('consolidate', retrieval_consolidator)

    # graph.add_conditional_edge(
    #     'search_step',
    #     check_loop_condition,
    #     {
    #         'loop': 'consolidate',
    #         'complete': 'synthesizer'
    #     }
    # )
    graph.add_edge('synthesizer', graph.END)


5. Compile and Run the Graph
----------------------------
Compile the graph to prepare it for execution, then run it with an initial state.

.. code-block:: python

    # ... (full graph definition)

    runner = graph.compile()
    initial_state: SearchState = {
        "user_query": "What are the key differences between Orkes Conductor and Temporal?",
        "search_queries": [],
        "current_index": 0,
        "raw_results": [],
        "is_finished": False,
        "final_answer": ""
    }

    print("Running graph...")
    runner.run(initial_state)
    print("Graph execution complete.")


6. Visualize the Graph Execution
--------------------------------
Orkes provides a visualization tool to inspect the flow and state changes during execution.

.. code-block:: python

    # ... (after runner.run(initial_state))

    runner.visualize_trace()
    print("Graph visualization trace generated. Check your traces folder.")

For a complete and runnable example, please refer to `tests/examples/graph_service_test.py`.
