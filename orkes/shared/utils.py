from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import datetime
import ast
import inspect
import sys

def format_start_time(start_time: float) -> str:
    """
    Converts a Unix timestamp to a human-readable 'YYYY-MM-DD HH:MM:SS' format.

    Args:
        start_time (float): The Unix timestamp to convert.

    Returns:
        str: The formatted date and time string.
    """
    dt = datetime.datetime.fromtimestamp(start_time)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def format_elapsed_time(elapsed_seconds: float) -> str:
    """
    Formats a duration in seconds into a human-readable string with minutes,
    seconds, milliseconds, and microseconds.

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

class ToolParameter(BaseModel):
    """
    Represents the JSON Schema for the parameters of a tool.

    This class defines the structure of the parameters that a tool can accept,
    following the JSON Schema specification.

    Attributes:
        type (str): The type of the parameter, which is 'object' by default.
        properties (Dict[str, Any]): A dictionary defining the properties of the
                                    object, where each key is a parameter name and
                                    the value is its schema.
        required (Optional[List[str]]): A list of required parameter names.
    """
    type: str = "object"
    properties: Dict[str, Any]
    required: Optional[List[str]] = None

class ToolDefinition(BaseModel):
    """
    A universal schema for defining a tool that can be used by an LLM, with methods
    to convert the tool definition to different provider-specific formats.

    Attributes:
        name (str): The name of the tool.
        description (str): A description of what the tool does.
        parameters (ToolParameter): The schema for the parameters that the tool
                                   accepts.
    """
    name: str
    description: str
    parameters: ToolParameter

    def to_openai(self) -> Dict[str, Any]:
        """
        Converts the tool definition to the format expected by OpenAI and vLLM.
        """
        return {
            "type": "function",
            "function": self.model_dump()
        }

    def to_gemini(self) -> Dict[str, Any]:
        """
        Converts the tool definition to the format expected by Google Gemini.
        """
        dump = self.model_dump()
        return {
            "name": dump["name"],
            "description": dump["description"],
            "parameters": dump["parameters"]
        }

    def to_claude(self) -> Dict[str, Any]:
        """
        Converts the tool definition to the format expected by Anthropic Claude.
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters.model_dump()
        }


def get_instances_from_func(func, state, target_class):
    instances = []

    def tracer(frame, event, arg):
        # We look at the 'return' event to see all locals before they are destroyed
        if event == 'return':
            for var_name, value in frame.f_locals.items():
                if isinstance(value, target_class):
                    instances.append(value)
        return tracer

    # Set the trace and run the function
    sys.settrace(tracer)
    try:
        func(state)
    finally:
        sys.settrace(None) # Always stop tracing to prevent slowdowns
    
    return instances


def create_dict_from_typeddict(td_cls):
    # Mapping of types to their "zero-value" defaults
    type_defaults = {
        str: "",
        int: 0,
        bool: False,
        list: [],
        List: [],  # Handles typing.List
        dict: {}
    }
    
    # Extract annotations (keys and their types)
    # Using __annotations__ works even if typing.get_type_hints fails
    annotations = td_cls.__annotations__
    
    return {
        key: type_defaults.get(val_type, None) 
        for key, val_type in annotations.items()
    }
