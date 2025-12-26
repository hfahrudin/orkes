from contextvars import ContextVar
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from orkes.graph.schema import TracesSchema, EdgeTrace

edge_id_var: ContextVar[Optional[str]] = ContextVar("edge_id", default=None)
trace_var: ContextVar[Optional["TracesSchema"]] = ContextVar("trace", default=None)
edge_trace_var: ContextVar[Optional["EdgeTrace"]] = ContextVar("edge_trace", default=None)