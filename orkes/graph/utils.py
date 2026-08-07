import inspect
from typing import Callable
from functools import wraps
import time
from orkes.shared.context import edge_trace_var
from orkes.graph.schema import FunctionTraceSchema

def orkes_tracable(func):
    """
    A decorator that traces the input, output, and execution time of a function
    and records it in the current edge's trace.

    This decorator is intended to be used on functions that are part of an OrkesGraph.
    When a function decorated with `orkes_tracable` is executed during a traced
    graph run, its inputs, output, and execution time will be captured and added
    to the `function_traces` of the current edge trace.

    If the function is executed outside of a traced graph run, it will behave
    as if it were not decorated.

    If `func` is a coroutine function (`async def`), the decorated function is
    also a coroutine function -- `inspect.iscoroutinefunction` reports `True`
    on the wrapped result, and the wrapped call is awaited before the trace is
    recorded. This keeps coroutine-ness detectable through the decorator,
    which matters for anything (e.g. the graph runner) that branches on
    `inspect.iscoroutinefunction` to decide whether a function needs to be
    awaited.
    """
    def _build_trace(result, args, kwargs, elapsed):
        # Attempt to create the trace object once
        try:
            return FunctionTraceSchema(
                function_name=func.__name__,
                input_args=args,
                input_kwargs=kwargs,
                return_value=result, # Try original result
                elapsed=elapsed
            )
        except Exception:
            # Fallback if result isn't serializable
            return FunctionTraceSchema(
                function_name=func.__name__,
                input_args=args,
                input_kwargs=kwargs,
                return_value=str(result),
                elapsed=elapsed
            )

    if inspect.iscoroutinefunction(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            edge_trace = edge_trace_var.get()
            if not edge_trace:
                return await func(*args, **kwargs)

            start_time = time.time()
            result = await func(*args, **kwargs)
            elapsed = time.time() - start_time

            function_trace = _build_trace(result, args, kwargs, elapsed)

            if edge_trace.function_traces is None:
                edge_trace.function_traces = []

            edge_trace.function_traces.append(function_trace)
            return result
        return async_wrapper

    @wraps(func)
    def wrapper(*args, **kwargs):
        edge_trace = edge_trace_var.get()
        if not edge_trace:
            return func(*args, **kwargs)

        start_time = time.time()
        result = func(*args, **kwargs)
        elapsed = time.time() - start_time

        function_trace = _build_trace(result, args, kwargs, elapsed)

        if edge_trace.function_traces is None:
            edge_trace.function_traces = []

        edge_trace.function_traces.append(function_trace)
        return result
    return wrapper

def function_assertion(func: Callable, expected_type: type) -> bool:
    """
    Asserts that a function has at least one parameter with the expected type annotation.

    Args:
        func (Callable): The function to inspect.
        expected_type (type): The expected type annotation.

    Returns:
        bool: True if a parameter with the expected type is found, False otherwise.
    """
    sig = inspect.signature(func)
    for param in sig.parameters.values():
        if param.annotation is not inspect._empty:
            if param.annotation == expected_type:
                return True
    return False

def is_typeddict_class(obj) -> bool:
    """
    Checks if an object is a TypedDict class.

    Args:
        obj: The object to check.

    Returns:
        bool: True if the object is a TypedDict class, False otherwise.
    """
    return isinstance(obj, type) and issubclass(obj, dict) and hasattr(obj, '__annotations__') and getattr(obj, '__total__', None) is not None
