import importlib.metadata

try:
    __version__ = importlib.metadata.version("orkes")
except importlib.metadata.PackageNotFoundError:
    # Handle case where package is not installed (e.g., in development)
    __version__ = "0.0.0-dev"
