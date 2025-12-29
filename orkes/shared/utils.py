from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import datetime
import ast
import inspect
import sys

def format_start_time(start_time: float) -> str:
    """Converts a Unix timestamp to a human-readable 'YYYY-MM-DD HH:MM:SS' format.

    Args:
        start_time (float): The Unix timestamp to convert.

    Returns:
        str: The formatted date and time string.
    """
    dt = datetime.datetime.fromtimestamp(start_time)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def format_elapsed_time(elapsed_seconds: float) -> str:
    """Formats a duration in seconds into a human-readable string.

    The string includes minutes, seconds, milliseconds, and microseconds.

    Args:
        elapsed_seconds (float): The duration in seconds.

    Returns:
        str: The formatted duration string (e.g., 'Xm Ys Zms Wus').
    """
    total_us = int(elapsed_seconds * 1_000_000)

    total_seconds, microseconds = divmod(total_us, 1_000_000)
    minutes, seconds = divmod(total_seconds, 60)
    milliseconds, microseconds = divmod(microseconds, 1_000)

    return f"{minutes}m {seconds}s {milliseconds}ms {microseconds}us"

def get_instances_from_func(func, state, target_class):
    """Retrieves all instances of a target class created within a function.

    This function uses a trace to inspect the local variables of the given
    function and returns all instances of the target class.

    Args:
        func (Callable): The function to inspect.
        state: The state to pass to the function.
        target_class (type): The class to look for.

    Returns:
        list: A list of instances of the target class.
    """
    instances = []

    def tracer(frame, event, arg):
        if event == 'return':
            for var_name, value in frame.f_locals.items():
                if isinstance(value, target_class):
                    instances.append(value)
        return tracer

    sys.settrace(tracer)
    try:
        func(state)
    finally:
        sys.settrace(None)

    return instances


def create_dict_from_typeddict(td_cls):
    """Creates a dictionary with default values from a TypedDict class.

    This function takes a TypedDict class and creates a dictionary with keys
    matching the TypedDict's annotations, and values set to their "zero-value"
    defaults.

    Args:
        td_cls (type): The TypedDict class to use.

    Returns:
        dict: A dictionary with default values.
    """
    type_defaults = {
        str: "",
        int: 0,
        bool: False,
        list: [],
        List: [],
        dict: {}
    }

    annotations = td_cls.__annotations__

    return {
        key: type_defaults.get(val_type, None)
        for key, val_type in annotations.items()
    }
