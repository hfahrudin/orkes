from pydantic import BaseModel
from typing import List

class OrkesMessageSchema(BaseModel):
    """Schema for a single message in an Orkes LLM conversation."""
    role: str
    content: str

class OrkesMessagesSchema(BaseModel):
    """Schema for LLM request payload containing a list of messages."""
    messages: List[OrkesMessageSchema]
