from pydantic import BaseModel
from typing import List

class OrkesToolSchema(BaseModel):
    """Schema for a tool definition in Orkes."""
    name: str
    description: str
    parameters: dict

class OrkesMessageSchema(BaseModel):
    """Schema for a single message in an Orkes LLM conversation."""
    role: str
    content: str

class OrkesMessagesSchema(BaseModel):
    """Schema for LLM request payload containing a list of messages."""
    messages: List[OrkesMessageSchema]
