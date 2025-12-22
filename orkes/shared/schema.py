from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class ToolParameter(BaseModel):
    """Represents the JSON Schema for tool parameters."""
    type: str = "object"
    properties: Dict[str, Any]
    required: Optional[List[str]] = None

class OrkesToolSchema(BaseModel):
    """A universal tool definition schema."""
    name: str
    description: str
    parameters: ToolParameter

class OrkesMessageSchema(BaseModel):
    """Schema for a single message in an Orkes LLM conversation."""
    role: str
    content: str

class OrkesMessagesSchema(BaseModel):
    """Schema for LLM request payload containing a list of messages."""
    messages: List[OrkesMessageSchema]
