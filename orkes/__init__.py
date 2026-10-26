def __getattr__(name):
    # `__version__` is looked up on first access rather than at import time,
    # since importlib.metadata is the slowest part of importing orkes.
    if name == "__version__":
        import importlib.metadata

        try:
            return importlib.metadata.version("orkes")
        except importlib.metadata.PackageNotFoundError:
            # Package not installed (e.g., in development)
            return "0.0.0-dev"
    raise AttributeError(f"module 'orkes' has no attribute {name!r}")
