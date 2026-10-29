"""Trace sinks: objects that receive a graph's trace while it runs.

Attach them with `OrkesGraph(..., trace_sinks=[...])`. orkes calls each method
at a fixed point of every run; a sink that raises is logged and skipped, so it
can never break the run. Subclass `TraceSink` and override only what you need.

`WatcherSink` (in `orkes.exporters.watcher`) sends traces to Orkes Watcher.
"""
from orkes.graph.schema import EdgeTrace, TracesSchema


class TraceSink:
    """Receives a run's trace as it happens. Every method is optional.

    Methods are called from the thread running the graph and should return
    quickly (queue the data and send it elsewhere). Under `arun()`,
    `on_run_end` runs in a worker thread, so it may wait briefly to flush.
    The current run's trace is also available as `orkes.shared.context.trace_var`.
    """

    def on_run_start(self, trace: TracesSchema) -> None:
        """A run started. `trace` has its run_id, graph name and node list,
        and no edges yet."""

    def on_edge(self, edge_trace: EdgeTrace) -> None:
        """An edge traversal finished (successfully or not) and was added to
        the trace. Parallel branch edges arrive before their parent edge."""

    def on_run_end(self, trace: TracesSchema) -> None:
        """The run finished or failed. `trace` has its final status,
        elapsed_time, error and failed_node."""


__all__ = ["TraceSink"]
