import inspect
from typing import Callable
import random

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

def check_dict_values_type(d: dict, cls: type) -> bool:
    """
    Checks if all values in a dictionary are of a certain type.

    Args:
        d (dict): The dictionary to check.
        cls (type): The expected type of the values.

    Returns:
        bool: True if all values are of the specified type, False otherwise.
    """
    return all(isinstance(v, cls) for v in d.values())

def randomize_color_hex() -> str:
    """
    Generates a random hex color code.

    Returns:
        str: A random hex color code in the format "#RRGGBB".
    """
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))
