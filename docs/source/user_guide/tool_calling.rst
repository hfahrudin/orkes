.. _tool_calling:

==============
Tool Calling
==============

Orkes provides a flexible way to integrate external tools into your workflows. The current implementation gives you fine-grained control over how tools are defined and used.

Defining a Tool
---------------

You can define a tool using ``orkes.shared.schema.OrkesToolSchema``. This schema describes the tool's name, description, and the parameters it accepts. The parameter schema follows the JSON Schema standard.

Here's an example of how to define a ``get_weather`` tool:

.. code-block:: python

    from orkes.shared.schema import OrkesToolSchema

    orkes_tool = OrkesToolSchema(
        name="get_weather",
        description="Get the current weather in a given location",
        parameters={
            "type": "object",
            "properties": {
                "location": {
                    "type": "string",
                    "description": "The city and state, e.g. San Francisco, CA",
                },
            },
            "required": ["location"],
        }
    )


.. mermaid::

    sequenceDiagram
        participant User
        participant Application (Orkes)
        participant LLM

        User->>Application: "What is the weather in San Francisco?"
        Application->>LLM: send_message(messages, tools=[get_weather_tool])
        LLM-->>Application: response with tool_calls
        Application->>Application: Execute get_weather("San Francisco")
        Application->>LLM: send_message(messages=[..., tool_result])
        LLM-->>Application: Final weather report
        Application-->>User: Here is the weather...

.. code-block:: python

    from orkes.shared.schema import OrkesMessagesSchema
    # Assuming you have an `openai_client` instance configured

    messages = OrkesMessagesSchema(messages=[{"role": "user", "content": "What is the weather in San Francisco?"}])

    # The 'orkes_tool' is the same as defined above
    response = openai_client.send_message(messages, tools=[orkes_tool])

    # response['content'] is the dumped RequestSchema: {"content_type": ..., "content": ...}
    # content_type is "tool_calls" if the LLM decided to use a tool, or "message" for plain text.
    if response["content"]["content_type"] == "tool_calls":
        # 'content' is then a list of dumped ToolCallSchema dicts: {"function_name": ..., "arguments": {...}}
        for tool_call in response["content"]["content"]:
            if tool_call["function_name"] == "get_weather":
                # ... call your actual get_weather function with tool_call["arguments"] ...
                pass
    else:
        print(response["content"]["content"])  # plain text reply


Using Python Functions Directly as Tools
----------------------------------------

Orkes simplifies tool definition by allowing you to pass a standard Python function directly to the ``tools`` argument of ``send_message``. Orkes will automatically inspect the function's signature (including type hints and docstrings) and convert it into an ``OrkesToolSchema``. This significantly reduces boilerplate when defining simple tools.

Here's how you can achieve the same ``get_weather`` tool definition using a Python function:

.. code-block:: python

    from orkes.shared.schema import OrkesMessagesSchema
    # Assuming you have an `openai_client` instance configured

    def get_weather(location: str) -> str:
        """
        Get the current weather in a given location.

        Args:
            location: The city and state, e.g. "San Francisco, CA"
        """
        # In a real application, this would call an external weather API
        if "San Francisco" in location:
            return "It's foggy and 15°C in San Francisco."
        return f"Weather for {location} is currently unknown."

    messages = OrkesMessagesSchema(messages=[{"role": "user", "content": "What is the weather in San Francisco?"}])

    # Pass the Python function directly to the tools argument
    response = openai_client.send_message(messages, tools=[get_weather])

    if response["content"]["content_type"] == "tool_calls":
        for tool_call in response["content"]["content"]:
            if tool_call["function_name"] == "get_weather":
                # Execute the function with arguments from the LLM's tool call
                weather_report = get_weather(**tool_call["arguments"])
                print(f"Weather report: {weather_report}")
                # ... send the tool result back to the LLM ...
