import inspect
from typing import Callable

def function_assertion(func: Callable, expected_type: type) -> bool:
    sig = inspect.signature(func)
    for param in sig.parameters.values():
        if param.annotation is not inspect._empty:
            if param.annotation == expected_type:
                return True
    return False



def is_typeddict_class(obj) -> bool:
    return isinstance(obj, type) and issubclass(obj, dict) and hasattr(obj, '__annotations__') and getattr(obj, '__total__', None) is not None
