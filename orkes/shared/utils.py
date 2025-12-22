from typing import Any, Dict, List, Optional
from pydantic import BaseModel

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
