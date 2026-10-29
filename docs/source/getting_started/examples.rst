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

7. Send Runs to Orkes Watcher
-----------------------------
To see runs live in `Orkes Watcher <https://github.com/hfahrudin/orkes-watcher>`__ and keep their history, attach a ``WatcherSink`` to the graph. The graph itself doesn't change.

.. code-block:: python

    from orkes.exporters.watcher import WatcherSink

    sink = WatcherSink(api_key="<project ingest key>", base_url="http://localhost:8000")
    graph = OrkesGraph(SearchState, name="search-example", trace_sinks=[sink])

Below is the full search graph with a sink attached. It runs twice: once successfully, and once with a search that fails, so both cases show up in the dashboard. It also uses ``redact`` to keep the user's question out of the watcher. It needs no LLM or API key other than the watcher's.

Save the code below as ``watcher_example.py`` and run it with your project's ingest key:

.. code-block:: bash

    ORKES_WATCHER_KEY=<project ingest key> python watcher_example.py

.. code-block:: python

    import os
    import time
    from typing import List, TypedDict

    from orkes.graph.core import OrkesGraph
    from orkes.exporters.watcher import WatcherSink


    class SearchState(TypedDict):
        user_query: str
        search_queries: List[str]
        current_index: int
        raw_results: List[str]
        final_answer: str


    def planner(state: SearchState):
        """Splits the question into search queries."""
        return {"search_queries": [f"{state['user_query']} overview", f"{state['user_query']} comparison"],
                "current_index": 0, "raw_results": []}


    def search_step(state: SearchState):
        """Runs the next search query."""
        query = state["search_queries"][state["current_index"]]
        time.sleep(0.3)  # stands in for a real search call
        if "fail" in query:
            raise ConnectionError(f"search service timed out for '{query}'")
        return {"raw_results": state["raw_results"] + [f"results for '{query}'"],
                "current_index": state["current_index"] + 1}


    def has_more_queries(state: SearchState):
        return "more" if state["current_index"] < len(state["search_queries"]) else "done"


    def synthesizer(state: SearchState):
        """Writes the final answer from the search results."""
        return {"final_answer": f"Answer based on {len(state['raw_results'])} searches."}


    def redact(event):
        """Keeps the user's question out of the watcher."""
        snapshot = event.get("state_snapshot")
        if snapshot and "user_query" in snapshot:
            event = {**event, "state_snapshot": {**snapshot, "user_query": "[redacted]"}}
        return event


    sink = WatcherSink(
        api_key=os.environ["ORKES_WATCHER_KEY"],
        base_url=os.environ.get("ORKES_WATCHER_URL", "http://localhost:8000"),
        redact=redact,
    )

    graph = OrkesGraph(SearchState, name="search-example",
                       description="Plans searches, runs them one by one, then answers.",
                       trace_sinks=[sink])
    graph.add_node("planner", planner)
    graph.add_node("search_step", search_step)
    graph.add_node("synthesizer", synthesizer)
    graph.add_edge(graph.START, "planner")
    graph.add_edge("planner", "search_step")
    graph.add_conditional_edge("search_step", has_more_queries, {"more": "search_step", "done": "synthesizer"})
    graph.add_edge("synthesizer", graph.END)
    runner = graph.compile()


    def empty_state(question: str) -> SearchState:
        return {"user_query": question, "search_queries": [], "current_index": 0,
                "raw_results": [], "final_answer": ""}


    if __name__ == "__main__":
        result = runner.run(empty_state("Orkes vs Temporal"))
        print("finished:", result["final_answer"], "| run", runner.run_id)

        try:
            runner.run(empty_state("fail on purpose"))  # shows a failed run in the watcher
        except ConnectionError as e:
            print("failed:", e, "| run", runner.run_id)

In the watcher, open **Traces** and filter by the graph ``search-example``:

- The finished run shows the ``search_step`` loop (taken twice) and a state snapshot for each step.
- The failed run shows ``failed in search_step`` with the ``ConnectionError`` and its traceback.

See :ref:`orkes_watcher` for what is sent, how sending behaves, and how to write your own trace sink.
