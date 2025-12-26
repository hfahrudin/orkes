from typing import Any, Dict, List, Optional, Callable
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
        function (Callable): The actual callable function for the tool.
    """
    name: str
    description: str
    parameters: ToolParameter
    function: Callable

    model_config = {
        "arbitrary_types_allowed": True
    }

class OrkesMessageSchema(BaseModel):
    """
    Represents a single message in a conversation with an LLM.

    Attributes:
        role (str): The role of the message's author, such as 'user', 'system', 
                    'assistant', or 'tool'.
        content (Union[str, List[Dict], None]): The content of the message. Can be a string,
                                     a list of dictionaries (for tool calls),
                                     or None.
        content_type (Optional[str]): The type of content, e.g., 'tool_calls'.
        tool_call_id (Optional[str]): The ID of the tool call, used for messages with
                                   the 'tool' role.
    """
    role: str
    content: Union[str, List[Dict], None]
    content_type: Optional[str] = None
    tool_call_id: Optional[str] = None


class OrkesMessagesSchema(BaseModel):
    """
    Represents a list of messages to be sent to an LLM as part of a request.

    Attributes:
        messages (List[OrkesMessageSchema]): A list of messages.
    """
    messages: List[OrkesMessageSchema]



class ToolDefinition(BaseModel):
    """
    A universal schema for defining a tool that can be used by an LLM, with methods
    to convert the tool definition to different provider-specific formats.

    Attributes:
        name (str): The name of the tool.
        description (str): A description of what the tool does.
        parameters (ToolParameter): The schema for the parameters that the tool
                                   accepts.
    """
    name: str
    description: str
    parameters: ToolParameter

    def to_openai(self) -> Dict[str, Any]:
        """
        Converts the tool definition to the format expected by OpenAI and vLLM.
        """
        return {
            "type": "function",
            "function": self.model_dump()
        }

    def to_gemini(self) -> Dict[str, Any]:
        """
        Converts the tool definition to the format expected by Google Gemini.
        """
        dump = self.model_dump()
        return {
            "name": dump["name"],
            "description": dump["description"],
            "parameters": dump["parameters"]
        }

    def to_claude(self) -> Dict[str, Any]:
        """
        Converts the tool definition to the format expected by Anthropic Claude.
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters.model_dump()
        }
