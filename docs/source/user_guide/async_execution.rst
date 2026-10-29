.. _async_execution:

=================
Async Execution
=================

Node and gate functions can be ``async def``. A compiled graph runs via either
``run()`` (sync) or ``arun()`` (async-native) -- neither wraps the other.

.. mermaid::

    flowchart LR
        G[Compiled graph] --> R["run()<br/>sync, any context"]
        G --> A["arun()<br/>await from async code"]
        R -.->|"async node/gate present"| E["RuntimeError<br/>(fails before any node runs)"]

.. list-table::
   :header-rows: 1

   * -
     - ``run()``
     - ``arun()``
   * - Caller context
     - Any (script, notebook, cron)
     - Must be awaited from async code
   * - Node/gate functions allowed
     - ``def`` only
     - ``def`` and ``async def``, freely mixed
   * - Sync function execution
     - Called directly
     - Called directly (not offloaded to a thread)
   * - Async function execution
     - Not allowed -- raises ``RuntimeError``
     - Awaited natively

1. When to Reach for ``async def``
-------------------------------------

.. list-table::
   :header-rows: 1

   * - Node does...
     - Use
   * - An LLM call, HTTP request, DB query, or any ``await``-able I/O
     - ``async def`` + ``arun()``
   * - Pure in-memory computation, no I/O
     - ``def`` -- either ``run()`` or ``arun()`` works

2. Mixed Graph Example
------------------------

Full, runnable example -- an async node (real ``await``), an async gate
function, and a sync node, all in one graph:

.. code-block:: python

    import asyncio
    from typing import TypedDict
    from orkes.graph.core import OrkesGraph

    class MyState(TypedDict):
        query: str
        result: str
        attempts: int

    async def call_llm_node(state: MyState) -> MyState:
        state['result'] = await llm_client.stream_message(...)  # real await
        state['attempts'] += 1
        return state

    def format_node(state: MyState) -> MyState:
        state['result'] = state['result'].strip()
        return state

    async def is_good_enough(state: MyState) -> str:
        await asyncio.sleep(0)  # gate functions can be async too
        return 'done' if state['result'] else 'retry'

    graph = OrkesGraph(MyState)
    graph.add_node('call_llm', call_llm_node)
    graph.add_node('format', format_node)
    graph.add_edge(graph.START, 'call_llm')
    graph.add_conditional_edge('call_llm', is_good_enough, {
        'retry': 'call_llm',
        'done': 'format',
    })
    graph.add_edge('format', graph.END)

    app = graph.compile()
    result = asyncio.run(app.arun({'query': 'hi', 'result': '', 'attempts': 0}))

3. Fail-Fast Detection
------------------------

``app.has_async_components`` is computed once at ``compile()``. Calling
``run()`` on such a graph raises immediately -- before any state is touched or
node executed -- instead of silently returning an un-awaited coroutine:

.. code-block:: text

    RuntimeError: This graph contains an async node function or async
    conditional gate function; use arun() instead of run().

4. Concurrent Runs
--------------------

A ``GraphRunner`` holds per-run state (``graph_state``, ``trace``, step
counter) as instance attributes. One instance can only run once at a time --
a second concurrent call on the same instance raises:

.. code-block:: text

    RuntimeError: This GraphRunner instance is already executing a run; each
    concurrent execution needs its own compile()'d instance -- e.g.
    [graph.compile() for _ in range(n)], not one instance reused across
    concurrent run()/arun() calls.

.. mermaid::

    flowchart TB
        subgraph Correct["Correct: one instance per concurrent run"]
            direction LR
            C1["compile()"] --> I1[Instance A] --> Ra["arun(s1)"]
            C2["compile()"] --> I2[Instance B] --> Rb["arun(s2)"]
        end
        subgraph Wrong["Wrong: same instance, concurrently"]
            direction LR
            I3[Instance A] --> Rc["arun(s1)"]
            I3 --> Rd["arun(s2)"]
            Rc -.-> X["RuntimeError"]
            Rd -.-> X
        end

.. code-block:: python

    # Correct
    apps = [graph.compile() for _ in range(3)]
    results = await asyncio.gather(*(app.arun(s) for app in apps))

    # Incorrect -- raises RuntimeError
    app = graph.compile()
    await asyncio.gather(app.arun(s1), app.arun(s2))

5. What Doesn't Change
-------------------------

.. list-table::
   :header-rows: 1

   * - Behavior
     - Under ``run()``
     - Under ``arun()``
   * - Parallel branches (:ref:`advanced_control_flow`)
     - Sequential, isolated deep-copied state
     - Same -- still sequential, still isolated
   * - Tracing / ``visualize_trace()``
     - Same ``TracesSchema`` structure
     - Identical structure

Concurrent branch execution (via ``asyncio.gather`` across branches) is not
yet supported -- it needs a different internal state model than
``GraphRunner`` uses today.

6. Coroutine vs. Thread: Why ``arun()`` Exists
-------------------------------------------------

Wrapping sync ``run()`` in a thread pool already gives concurrency for
I/O-bound work -- so why build ``arun()`` at all?

.. mermaid::

    sequenceDiagram
        participant EventLoop as Event loop, one thread
        participant CoroA as Coroutine A
        participant CoroB as Coroutine B
        EventLoop->>CoroA: resume
        CoroA->>CoroA: run until await
        CoroA-->>EventLoop: suspend
        EventLoop->>CoroB: resume
        CoroB->>CoroB: run until await
        CoroB-->>EventLoop: suspend
        Note over EventLoop: both waiting concurrently, one thread total
        EventLoop->>CoroA: resume when ready
        EventLoop->>CoroB: resume when ready

.. list-table::
   :header-rows: 1

   * -
     - Thread pool + ``run()``
     - ``arun()``
   * - Speedup for I/O-bound work
     - Same (measured: ~4.9x for 5 concurrent calls)
     - Same (measured: ~5.0x)
   * - Node can natively ``await``
     - No
     - Yes
   * - Cost per concurrent unit
     - MB-scale OS thread
     - KB-scale coroutine frame
   * - Cancel one in-flight run cleanly
     - Not possible
     - ``task.cancel()`` at the next ``await``
   * - Switch point
     - Anywhere (OS-scheduled)
     - Only at ``await`` (explicit in code)
