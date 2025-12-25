from contextvars import ContextVar
from typing import Optional

from orkes.graph.schema import TracesSchema

edge_id_var: ContextVar[Optional[str]] = ContextVar("edge_id", default=None)
trace_var: ContextVar[Optional[TracesSchema]] = ContextVar("trace", default=None)