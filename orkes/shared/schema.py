from typing import Any, Dict, List, Optional
from pydantic import BaseModel

class ToolParameter(BaseModel):
    """
    Represents the JSON Schema for the parameters of a tool.

    This class defines the structure of the parameters that a tool can accept,
    following the JSON Schema specification.

    Attributes:
        type (str): The type of the parameter, which is 'object' by default.
        properties (Dict[str, Any]): A dictionary defining the properties of the
                                    object, where each key is a parameter name and
                                    the value is its schema.
        required (Optional[List[str]]): A list of required parameter names.
    """
    type: str = "object"
    properties: Dict[str, Any]
    required: Optional[List[str]] = None

class OrkesToolSchema(BaseModel):
    """
    A universal schema for defining a tool that can be used by an LLM.

    Attributes:
        name (str): The name of the tool.
        description (str): A description of what the tool does.
        parameters (ToolParameter): The schema for the parameters that the tool
                                   accepts.
    """
    name: str
    description: str
    parameters: ToolParameter

class OrkesMessageSchema(BaseModel):
    """
    Represents a single message in a conversation with an LLM.

    Attributes:
        role (str): The role of the message's author, such as 'user', 'system', or
                    'assistant'.
        content (str): The content of the message.
    """
    role: str
    content: str

class OrkesMessagesSchema(BaseModel):
    """
    Represents a list of messages to be sent to an LLM as part of a request.

    Attributes:
        messages (List[OrkesMessageSchema]): A list of messages.
    """
    messages: List[OrkesMessageSchema]
