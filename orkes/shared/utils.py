from typing import Callable, Union
import typing
import datetime
import inspect
from orkes.shared.schema import OrkesToolSchema, ToolParameter


_JSON_TYPE_MAPPING = {
    'str': 'string',
    'int': 'integer',
    'float': 'number',
    'bool': 'boolean',
    'list': 'array',
    'dict': 'object',
}


def _annotation_to_json_type(annotation) -> str:
    """Resolves a type annotation to a JSON Schema type name.

    Handles plain builtins (str/int/float/bool/list/dict) as well as
    `typing` generics such as `List[str]`, `Dict[str, Any]`, and
    `Optional[int]` (via their `typing.get_origin`), which don't expose a
    `__name__` attribute the way builtins do.

    Args:
        annotation: The type annotation to resolve.

    Returns:
        str: The corresponding JSON Schema type name, defaulting to 'string'
             if the annotation can't be resolved (e.g. multi-type Unions).
    """
    origin = typing.get_origin(annotation)

    if origin is Union:
        non_none_args = [arg for arg in typing.get_args(annotation) if arg is not type(None)]
        if len(non_none_args) == 1:
            return _annotation_to_json_type(non_none_args[0])
        return 'string'

    if origin is not None:
        return _JSON_TYPE_MAPPING.get(getattr(origin, '__name__', ''), 'string')

    return _JSON_TYPE_MAPPING.get(getattr(annotation, '__name__', ''), 'string')


def callable_to_orkes_tool_schema(fn: Callable) -> OrkesToolSchema:
    """
    Converts a Python function into an OrkesToolSchema.

    This function inspects a callable, extracts its signature and docstring,
    and constructs an OrkesToolSchema that can be used within the Orkes framework.
    The docstring is expected to be in a format that includes a main description
    and an 'Args' section for parameter details.

    Args:
        fn (Callable): The function to convert.

    Returns:
        OrkesToolSchema: A schema representing the function as a tool.
    """
    signature = inspect.signature(fn)
    docstring = inspect.getdoc(fn) or ""
    doc_parts = docstring.split('Args:')
    description = doc_parts[0].strip()
    args_description = doc_parts[1].strip() if len(doc_parts) > 1 else ""

    lines = [line.strip() for line in args_description.split('\n')]
    param_docs = {}
    for line in lines:
        if ':' in line:
            name_part, desc = line.split(':', 1)
            name = name_part.split('(')[0].strip()
            param_docs[name] = desc.strip()

    properties = {}
    required = []

    for name, param in signature.parameters.items():
        if name in ('self', 'cls'):
            continue

        param_type = 'string'  # Default type
        if param.annotation != inspect.Parameter.empty:
            param_type = _annotation_to_json_type(param.annotation)

        properties[name] = {
            'type': param_type,
            'description': param_docs.get(name, '')
        }

        if param.default == inspect.Parameter.empty:
            required.append(name)
        else:
            properties[name]['default'] = param.default

    tool_parameters = ToolParameter(
        type="object",
        properties=properties,
        required=required if required else None
    )

    return OrkesToolSchema(
        name=fn.__name__,
        description=description,
        parameters=tool_parameters
    )


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
