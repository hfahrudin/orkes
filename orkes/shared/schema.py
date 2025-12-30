from typing import Any, Dict, List, Optional, Callable, Union
from pydantic import BaseModel


class ToolCallSchema(BaseModel):
    """Represents a tool call requested by the LLM.

    This schema defines the structure of a tool call, which includes the name of the
    function to be called and the arguments to pass to it.

    Attributes:
        function_name (str): The name of the function to be called.
        arguments (Dict[str, Any]): A dictionary of arguments for the function.
    """
    function_name: str
    arguments: Dict[str, Any]

class RequestSchema(BaseModel):
    """Represents a standard response from an LLM.

    This schema defines the structure of a response from an LLM, which can be either
    a string of content or a list of tool calls.

    Attributes:
        content_type (str): The type of content in the response, either 'text' or
                            'tool_calls'.
        content (Union[str, List[ToolCallSchema]]): The content of the response.
    """
    content_type: str
    content : Union[str, List[ToolCallSchema]]


class ToolParameter(BaseModel):
    """Represents the JSON Schema for the parameters of a tool.

    This class defines the structure of the parameters that a tool can accept,
    following the JSON Schema specification. This allows for clear and
    unambiguous definition of a tool's inputs.

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
    """A universal schema for defining a tool that can be used by an LLM.

    This schema is used to define a tool that can be used by an LLM. It contains
    all the necessary information for the LLM to understand what the tool does,
    what parameters it accepts, and how to call it.

    Attributes:
        name (str): The name of the tool.
        description (str): A description of what the tool does.
        parameters (ToolParameter): The schema for the parameters that the tool
                                   accepts.
        function (Callable, optional): The actual callable function for the tool.
                                       Defaults to None.
    """
    name: str
    description: str
    parameters: ToolParameter
    function: Optional[Callable] = None

    model_config = {
        "arbitrary_types_allowed": True
    }

class OrkesMessageSchema(BaseModel):
    """Represents a single message in a conversation with an LLM.

    This schema is used to represent a single message in a conversation with an
    LLM. A conversation is typically a sequence of messages, where each message
    has a role, content, and optionally a content type and tool call ID.

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
    """Represents a list of messages to be sent to an LLM as part of a request.

    This is a container for a list of `OrkesMessageSchema` objects, representing
    a complete conversation or a turn in a conversation.

    Attributes:
        messages (List[OrkesMessageSchema]): A list of messages.
    """
    messages: List[OrkesMessageSchema]



class ToolDefinition(BaseModel):
    """A universal schema for defining a tool that can be used by an LLM.

    This schema provides methods to convert the tool definition to different
    provider-specific formats, such as for OpenAI, Google Gemini, and Anthropic
    Claude.

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
        """Converts the tool definition to the format expected by OpenAI and vLLM.

        Returns:
            Dict[str, Any]: The tool definition in OpenAI's format.
        """
        return {
            "type": "function",
            "function": self.model_dump()
        }

    def to_gemini(self) -> Dict[str, Any]:
        """Converts the tool definition to the format expected by Google Gemini.

        Returns:
            Dict[str, Any]: The tool definition in Gemini's format.
        """
        dump = self.model_dump()
        return {
            "name": dump["name"],
            "description": dump["description"],
            "parameters": dump["parameters"]
        }

    def to_claude(self) -> Dict[str, Any]:
        """Converts the tool definition to the format expected by Anthropic Claude.

        Returns:
            Dict[str, Any]: The tool definition in Claude's format.
        """
        return {
            "name": self.name,
            "description": self.description,
            "input_schema": self.parameters.model_dump()
        }
