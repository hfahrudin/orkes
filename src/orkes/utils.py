import inspect
from typing import Callable

def function_assertion(func: Callable, expected_type: type) -> bool:
    sig = inspect.signature(func)
    for param in sig.parameters.values():
        if param.annotation is not inspect._empty:
            if param.annotation == expected_type:
                return True
    return False
