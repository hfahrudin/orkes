"""This module defines `ContextVar` objects for propagating contextual information.

These context variables allow trace and execution-specific data to be accessible
throughout a call chain without explicit parameter passing, which is particularly
useful in asynchronous and concurrent operations within the Orkes framework.
"""

from contextvars import ContextVar
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from orkes.graph.schema import TracesSchema, EdgeTrace

#: Context variable for storing the ID of the currently executing graph edge.
#:
#: This allows components deeper in the call stack to access the ID of the edge
#: that triggered their execution.
edge_id_var: ContextVar[Optional[str]] = ContextVar("edge_id", default=None)

#: Context variable for storing the main `TracesSchema` object for the current
#: graph execution run.
#:
#: This enables collection of various trace data (nodes, edges, LLM calls)
#: across different parts of the graph execution.
trace_var: ContextVar[Optional["TracesSchema"]] = ContextVar("trace", default=None)

#: Context variable for storing the `EdgeTrace` object for the currently
#: executing graph edge.
#:
#: This allows LLM calls and other edge-specific events to be directly
#: appended to the correct edge's trace.
edge_trace_var: ContextVar[Optional["EdgeTrace"]] = ContextVar("edge_trace", default=None)