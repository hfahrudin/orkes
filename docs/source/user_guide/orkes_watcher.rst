.. _orkes_watcher:

==========================
Sending Traces to Watcher
==========================

`Orkes Watcher <https://github.com/hfahrudin/orkes-watcher>`__ is a separate
web platform for Orkes traces. It shows your runs live while they execute and
keeps their history, so you can compare runs, see where they fail, and inspect
any run step by step.

Orkes talks to it through a **trace sink**: an object attached to a graph that
receives the trace as the run happens. ``WatcherSink`` is the sink for Orkes
Watcher. Nothing else in your graph code changes.

Setup
=====

``WatcherSink`` ships with Orkes, so a plain ``pip install orkes`` is enough.

1. In the watcher dashboard, open your project's **API keys** page and create
   an ingest key.

2. Attach a sink to your graph:

   .. code-block:: python

      from orkes.graph import OrkesGraph
      from orkes.exporters.watcher import WatcherSink

      sink = WatcherSink(
          api_key="<project ingest key>",
          base_url="http://localhost:8000",
      )

      graph = OrkesGraph(SearchState, name="search", trace_sinks=[sink])
      # ... add nodes and edges as usual
      runner = graph.compile()
      runner.run(initial_state)

``base_url`` is the watcher **backend** (port ``8000`` in the default deploy),
not the dashboard. The project's **Settings** page shows the address to use.

Create one sink and reuse it for all your graphs and runs. The ``name`` and
``description`` you give ``OrkesGraph``, and each node function's docstring,
show up in the dashboard, so it's worth setting them.

.. note::

   ``trace_sinks`` needs tracing. Passing it together with ``traced=False``
   raises a ``ValueError``.

What gets sent
==============

For every run, the watcher receives:

- the graph's name, description and nodes
- every edge traversal: where it went, when it started, how long the whole
  step took and how long the node's own function took, the state before the
  node ran, and the LLM calls and traced functions inside it
- the end of the run: ``FINISHED`` or ``FAILED``, the total time, and for a
  failed run the error with its traceback and the name of the node that failed

Data is sent **while the run is going**, so the dashboard updates live, not
only at the end.

Keeping secrets out
-------------------

**State snapshots, prompts and LLM replies are sent as they are.** To leave out
secrets or personal data, pass ``redact``: a function that receives each event
(and each node entry) as a ``dict`` and returns what should be sent instead.

.. code-block:: python

   def redact(event):
       if "state_snapshot" in event:
           event = {**event, "state_snapshot": {"redacted": True}}
       return event

   sink = WatcherSink(api_key=..., base_url=..., redact=redact)

If ``redact`` raises an error, that event is not sent and a warning is logged.

How sending behaves
===================

The watcher can never break or slow down your run beyond a small, fixed limit.

- **Your run only adds to a queue.** One background thread per sink does all
  the sending. It sends a run's events every 0.5 seconds, or sooner once 50
  are waiting, and stops by itself when there is nothing left to send.
- **End of a run.** ``run()`` / ``arun()`` waits **at most 3 seconds** at the
  end for that run's data to be sent, so a short script doesn't exit before
  it arrives. With a fast local watcher this is usually well under a second.
  Under ``arun()`` this wait happens in a worker thread, so it doesn't block
  the event loop.
- **Exit.** When the Python process exits, anything still queued gets one
  last send, again limited to 3 seconds in total.
- **Best effort.** A failed send is logged once per run and dropped. It is
  never retried, and it never raises into your code. If the watcher is
  down, the run carries on as if no sink were attached.
- **Size limits.** A single field over 256 KB (for example a very large
  state snapshot) is replaced by a marker saying it was too large; the
  dashboard shows it as *truncated*. At most 10,000 events are queued across
  all runs; past that, newer events are dropped with a warning.
- **Wrong key or incompatible watcher.** After a 401/403 response, or if the
  watcher doesn't support this version of the trace format, the sink logs one
  warning and stops sending for the rest of the process.

Warnings go to the ``orkes.watcher`` logger.

Killed processes
----------------

If a process is killed in the middle of a run, the run never sends its end.
The watcher shows it as *running* until the project's abandon timeout passes
(15 minutes, 30 minutes or 2 hours, set in the project's **Settings**), then marks it
*failed (abandoned)*. The steps sent before the process died are kept.

Version compatibility
=====================

Orkes and the watcher agree on a versioned trace format, the **contract**
(currently ``1.0``). Each request carries the contract version and the Orkes
version. On its first send, the sink asks the watcher which contract versions
it supports (``GET /version``); if this one isn't supported, it warns once and
sends nothing.

Orkes and the watcher can be upgraded independently as long as they share a
contract major version.

Writing your own sink
=====================

Any object with ``on_run_start``, ``on_edge`` and ``on_run_end`` methods can be
a trace sink. Subclass :class:`orkes.exporters.TraceSink` and override only
what you need:

.. code-block:: python

   from orkes.exporters import TraceSink

   class PrintSink(TraceSink):
       def on_edge(self, edge_trace):
           print(edge_trace.from_node, "->", edge_trace.to_node,
                 f"{edge_trace.elapsed:.3f}s")

       def on_run_end(self, trace):
           print(trace.status, trace.failed_node or "")

   graph = OrkesGraph(MyState, trace_sinks=[PrintSink()])

- ``on_run_start(trace)``: the run started. ``trace`` has its run id, graph
  name and nodes, and no edges yet.
- ``on_edge(edge_trace)``: one edge traversal finished, successfully or not.
  Parallel branch edges arrive before their parent edge.
- ``on_run_end(trace)``: the run finished or failed, with its final status,
  elapsed time, error and failed node.

Methods are called from the thread running the graph, so they should return
quickly: queue the data and send it elsewhere. A sink that raises is logged
and skipped; it can never break the run.
