import json
from dataclasses import dataclass, fields, is_dataclass
from typing import Any, Dict, List, Optional, Callable, Union


def to_dict(obj: Any, exclude: tuple = ()) -> Any:
    """Converts a schema object (and any nested ones) into plain dicts and lists.

    Unlike `dataclasses.asdict`, values are not deep-copied, so state holding
    objects that can't be copied (locks, clients) still converts.

    Args:
        obj: A schema dataclass, or a list/tuple/dict that may contain them.
        exclude (tuple): Field names to leave out of the top-level object.

    Returns:
        The same data built from dicts and lists.
    """
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: to_dict(getattr(obj, f.name)) for f in fields(obj) if f.name not in exclude}
    if isinstance(obj, (list, tuple)):
        return [to_dict(v) for v in obj]
    if isinstance(obj, dict):
        return {k: to_dict(v) for k, v in obj.items()}
    return obj


def to_json(obj: Any, **kwargs) -> str:
    """Serializes a schema object (or plain data) to JSON. Values JSON can't
    encode, such as datetimes or custom objects in state, are written with `str()`.

    The one serializer for traces, used both for saved trace files and by sinks.
    """
    return json.dumps(to_dict(obj), default=str, **kwargs)


@dataclass(kw_only=True)
class ToolCallSchema:
    """Represents a tool call requested by the LLM.

    This schema defines the structure of a tool call, which includes the name of the
    function to be called and the arguments to pass to it.

    Attributes:
        function_name (str): The name of the function to be called.
        arguments (Dict[str, Any]): A dictionary of arguments for the function.
        id (Optional[str]): The provider's id for this call. Pass it back as the
            `tool_call_id` of the tool result message.
    """
    function_name: str
    arguments: Dict[str, Any]
    id: Optional[str] = None


@dataclass(kw_only=True)
class RequestSchema:
    """Represents a standard response from an LLM.

    This schema defines the structure of a response from an LLM, which can be either
    a string of content or a list of tool calls.

    Attributes:
        content_type (str): The type of content in the response, either 'text' or
                            'tool_calls'.
        content (Union[str, List[ToolCallSchema]]): The content of the response.
    """
    content_type: str
    content: Union[str, List[ToolCallSchema]]


@dataclass(kw_only=True)
class ToolParameter:
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


@dataclass(kw_only=True)
class OrkesToolSchema:
    """A universal schema for defining a tool that can be used by an LLM.

    This schema is used to define a tool that can be used by an LLM. It contains
    all the necessary information for the LLM to understand what the tool does,
    what parameters it accepts, and how to call it.

    Attributes:
        name (str): The name of the tool.
        description (str): A description of what the tool does.
        parameters (ToolParameter): The schema for the parameters that the tool
                                   accepts. A plain dict is converted.
        function (Callable, optional): The actual callable function for the tool.
                                       Defaults to None.
    """
    name: str
    description: str
    parameters: ToolParameter
    function: Optional[Callable] = None

    def __post_init__(self):
        if isinstance(self.parameters, dict):
            self.parameters = ToolParameter(**self.parameters)


@dataclass(kw_only=True)
class OrkesMessageSchema:
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
        content_type (Optional[str]): The type of content. Set it to 'tool_calls'
            on an assistant message whose `content` is the list of tool calls the
            LLM returned, when sending them back as conversation history.
        tool_call_id (Optional[str]): The ID of the tool call, used for messages with
                                   the 'tool' role.

    Example (sending a tool result back)::

        reply = client.send_message(messages, tools=[get_weather])["content"]
        calls = reply["content"]  # list of {"function_name", "arguments", "id"}
        messages.messages.append(OrkesMessageSchema(role="assistant", content=calls, content_type="tool_calls"))
        for call in calls:
            result = get_weather(**call["arguments"])
            messages.messages.append(OrkesMessageSchema(role="tool", content=result, tool_call_id=call["id"]))
        final = client.send_message(messages, tools=[get_weather])
    """
    role: str
    content: Union[str, List[Dict], None]
    content_type: Optional[str] = None
    tool_call_id: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.role, str):
            raise TypeError(f"Message 'role' must be a str, got {type(self.role).__name__}.")


@dataclass(kw_only=True)
class OrkesMessagesSchema:
    """Represents a list of messages to be sent to an LLM as part of a request.

    This is a container for a list of `OrkesMessageSchema` objects, representing
    a complete conversation or a turn in a conversation.

    Attributes:
        messages (List[OrkesMessageSchema]): A list of messages. Plain dicts
            (e.g. ``{"role": "user", "content": "hi"}``) are converted.
    """
    messages: List[OrkesMessageSchema]

    def __post_init__(self):
        self.messages = [
            OrkesMessageSchema(**m) if isinstance(m, dict) else m
            for m in self.messages
        ]
