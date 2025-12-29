.. _features:

===============
Features
===============

Graph-based Workflows
---------------------
*   **OrkesGraph**: Define and manage intricate computational graphs that serve as the backbone for your AI workflows. These graphs allow for clear representation of dependencies and execution flow between different components. **The interface for defining these graphs is inspired by the well-known `NetworkX` library, providing a familiar and powerful paradigm for graph manipulation.**
*   **GraphRunner**: Execute the defined graphs efficiently, handling the orchestration of nodes and edges to process data and manage state transitions.
*   **Nodes and Edges**: Construct graphs using versatile `Node` and `Edge` primitives, including `ForwardEdge` for sequential steps and `ConditionalEdge` for branching logic based on dynamic conditions.
*   **Detailed Tracing**: Gain deep insights into graph execution with comprehensive tracing capabilities. Capture `NodeTrace`, `LLMTraceSchema`, `FunctionTraceSchema`, and `EdgeTrace` to monitor performance, debug issues, and understand the flow of information.

Agent System
--------------
*   **Agent and AgentInterface**: Develop and integrate sophisticated AI agents that can perform tasks, make decisions, and interact with various tools and services. The `AgentInterface` provides a structured way to define their capabilities and communication protocols.

LLM Integration
----------------
*   **UniversalLLMClient**: Interact seamlessly with a variety of Large Language Models through a unified client interface. This abstraction simplifies the process of switching between different LLM providers and managing their configurations.
*   **LLMFactory**: Dynamically create and configure LLM connections based on specified `LLMConfig` settings, ensuring flexible and scalable access to AI models.
*   **Pluggable Strategies**: Out-of-the-box support for popular LLM providers including `OpenAIStyleStrategy` (for OpenAI-compatible APIs), `AnthropicStrategy`, and `GoogleGeminiStrategy`, allowing you to leverage the best models for your use case. **Furthermore, Orkes empowers users to implement and integrate their own custom LLM strategies, extending support beyond the built-in solutions to any LLM service or local model.**

Tooling & Schema Management
----------------------------
*   **OrkesToolSchema**: Define custom tools that your agents or graph nodes can utilize, enabling them to interact with external APIs, databases, or custom functions in a structured manner.
*   **OrkesMessageSchema**: Standardized schemas for messages (`OrkesMessageSchema`, `OrkesMessagesSchema`) facilitate clear and consistent communication within your graph-based workflows and agent interactions.
*   **ToolDefinition and ToolParameter**: Precisely define the parameters and structure of your tools, ensuring proper invocation and data exchange.

Trace Visualization
--------------------
*   **TraceInspector**: Visualize the execution traces of your graphs and agents. The `TraceInspector` helps in understanding complex workflows, identifying bottlenecks, and debugging execution paths through an intuitive representation of traces.
