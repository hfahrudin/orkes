"""
This module defines `ContextVar` objects for propagating contextual information.
"""
from __future__ import annotations # Critical for clean Sphinx type-hinting
from contextvars import ContextVar
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from orkes.graph.schema import TracesSchema, EdgeTrace

#: Context variable for storing the ID of the currently executing graph edge.
edge_id_var: ContextVar[Optional[str]] = ContextVar("edge_id", default=None)
"""Context variable for storing the ID of the currently executing graph edge."""

#: Context variable for storing the main TracesSchema object.
trace_var: ContextVar[Optional[TracesSchema]] = ContextVar("trace", default=None)
"""Context variable for storing the main TracesSchema object."""

#: Context variable for storing the EdgeTrace object.
edge_trace_var: ContextVar[Optional[EdgeTrace]] = ContextVar("edge_trace", default=None)
"""Context variable for storing the EdgeTrace object."""
