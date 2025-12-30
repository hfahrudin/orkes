.. _tool_calling:

==============
Tool Calling
==============

Orkes provides a flexible way to integrate external tools into your workflows. While we are working on a fully automated tool calling system, the current implementation gives you fine-grained control over how tools are defined and used.

Defining a Tool
---------------

You can define a tool using the ``orkes.agents.schema.ToolSchema``. This schema describes the tool's name, description, and the parameters it accepts. The parameter schema follows the JSON Schema standard.

Here's an example of how to define a ``get_weather`` tool:

.. code-block:: python

    from orkes.agents.schema import ToolSchema

    orkes_tool = ToolSchema(
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

    # The response will contain a tool_calls attribute if the LLM decides to use the tool
    if response.tool_calls:
        # You can then process the tool call and send the result back to the LLM
        tool_call = response.tool_calls[0]
        if tool_call.function.name == "get_weather":
            # ... call your actual get_weather function ...
            pass
