from typing import Any, Dict, List, Optional
from pydantic import BaseModel
import datetime

def format_start_time(start_time: float) -> str:
    """
    Convert a Unix timestamp to 'YYYY-MM-DD HH:MM:SS'
    """
    dt = datetime.datetime.fromtimestamp(start_time)
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def format_elapsed_time(elapsed_seconds: float) -> str:
    """
    Format elapsed time as:
    'Xm Ys Zms Wus'

    - Minutes do not roll into hours
    - All units are always shown
    """
    total_us = int(elapsed_seconds * 1_000_000)

    total_seconds, microseconds = divmod(total_us, 1_000_000)
    minutes, seconds = divmod(total_seconds, 60)
    milliseconds, microseconds = divmod(microseconds, 1_000)

    return f"{minutes}m {seconds}s {milliseconds}ms {microseconds}us"

class ToolParameter(BaseModel):
    """Represents the JSON Schema for tool parameters."""
    type: str = "object"
    properties: Dict[str, Any]
    required: Optional[List[str]] = None

class ToolDefinition(BaseModel):
    """A universal tool definition schema."""
    name: str
    description: str
    parameters: ToolParameter

    def to_openai(self) -> Dict[str, Any]:
        """Format for OpenAI and vLLM."""
        return {
            "type": "function",
            "function": self.model_dump()
        }

    def to_gemini(self) -> Dict[str, Any]:
        """Format for Google Gemini (Function Declaration)."""
        # Gemini often prefers uppercase types in their schema docs
        dump = self.model_dump()
        return {
            "name": dump["name"],
            "description": dump["description"],
            "parameters": dump["parameters"]
        }

    def to_claude(self) -> Dict[str, Any]:
        """Format for Anthropic Claude."""
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters.model_dump()
        }
