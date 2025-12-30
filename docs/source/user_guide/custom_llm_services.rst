.. _custom_llm_services:

===========================
Connecting Custom LLMs
===========================

Orkes is designed to be provider-agnostic, allowing you to connect it to any LLM service. This guide provides a step-by-step example of how to create a custom "connector" for a hypothetical "EchoLLM".

Our "EchoLLM" is a simple service that just repeats the user's message back to them.

1. Define the Connector Class
-----------------------------
First, create a Python class for your connector. It's a good practice to have it accept any authentication tokens it might need during initialization.

.. code-block:: python

    from orkes.shared.schema import OrkesMessageSchema

    class EchoLlmConnector:
        def __init__(self, api_key: str):
            self.api_key = api_key
            # In a real connector, you would initialize an API client here

        def invoke(self, messages: list[OrkesMessageSchema]) -> OrkesMessageSchema:
            # This is the main method that Orkes will call.
            # It takes a list of messages and should return a single message.
            
            # In a real connector, you would make an API call here.
            # For our EchoLLM, we'll just simulate the response.
            last_user_message = next(
                (msg for msg in reversed(messages) if msg['role'] == 'user'), 
                None
            )

            response_content = "I echo: " + last_user_message['content'] if last_user_message else "I have nothing to echo."

            return OrkesMessageSchema(
                role="assistant",
                content=response_content
            )

2. Define the State and Node
----------------------------
Next, define the state for your graph and a node that will use your new connector. The node function will be responsible for creating an instance of your connector and calling its `invoke` method.

.. code-block:: python

    from typing import TypedDict
    from orkes.graph.core import OrkesGraph
    # ... (EchoLlmConnector class from above)

    class ChatState(TypedDict):
        user_input: str
        llm_response: str

    graph = OrkesGraph(ChatState)

    def llm_node(state: ChatState) -> ChatState:
        # 1. Instantiate the connector
        connector = EchoLlmConnector(api_key="dummy_key")

        # 2. Create the message to send to the LLM
        message = OrkesMessageSchema(role="user", content=state['user_input'])

        # 3. Invoke the connector and get the response
        response = connector.invoke([message])

        # 4. Update the state
        state['llm_response'] = response['content']
        return state

    graph.add_node('llm', llm_node)

3. Build and Run the Graph
--------------------------
Finally, connect the nodes, compile the graph, and run it.

.. code-block:: python

    # ... (graph and llm_node definition)
    from orkes.graph.runner import GraphRunner

    graph.add_edge(graph.START, 'llm')
    graph.add_edge('llm', graph.END)

    compiled_graph = graph.compile()
    runner = GraphRunner(compiled_graph)

    initial_state = ChatState(user_input="Hello, Orkes!", llm_response="")
    final_state = runner.run(initial_state)

    print(final_state)
    # Expected output: {'user_input': 'Hello, Orkes!', 'llm_response': 'I echo: Hello, Orkes!'}

By following this pattern, you can integrate any LLM service with Orkes. The key is to ensure your connector's `invoke` method receives a list of `OrkesMessageSchema` and returns a single `OrkesMessageSchema`.
