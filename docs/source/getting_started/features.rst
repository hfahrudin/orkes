.. _features:

========
Features
========

Orkes is designed with a focus on providing a clear, flexible, and powerful framework for building complex AI workflows. Here are some of the key features that make this possible:

Graph-based Architecture
------------------------
At the core of Orkes is the ``OrkesGraph``, a powerful abstraction for defining and managing computational workflows. This graph-based architecture allows you to represent complex logic as a collection of nodes and edges, providing a clear and intuitive way to visualize and control the flow of execution.

The interface for defining these graphs is inspired by the well-known `NetworkX <https://networkx.org/>`__ library, providing a familiar and powerful paradigm for those with experience in graph-based programming.

Key features of the graph architecture include:

- **Stateful Execution**: A shared state object is passed between nodes, allowing for seamless data flow and management throughout the graph's execution.
- **Flexible Control Flow**: Orkes supports both simple, unconditional edges for linear workflows and powerful conditional edges for creating branching logic and loops. This allows you to build dynamic and adaptive systems.
- **Simple, Pythonic Nodes**: Nodes in an Orkes graph are just plain Python functions, making it easy to integrate your existing code and logic into a graph-based workflow.

Graph Traceability and Visualization
------------------------------------
Understanding and debugging complex AI workflows is a major challenge. Orkes addresses this with a built-in traceability and visualization system. When you run a graph, Orkes can generate a detailed execution trace that captures the state, timing, and data flow at every step.

This trace can then be used to generate a self-contained, interactive HTML file that provides a visual representation of the graph's execution. This allows you to:

- **Visualize the execution path**: See exactly which nodes were executed and in what order.
- **Inspect the state at any point**: Understand how the data in your graph is being transformed.
- **Debug with ease**: Quickly identify bottlenecks, errors, and unexpected behavior.

Pluggable LLM Integrations
--------------------------
Orkes provides a flexible and extensible system for integrating with Large Language Models (LLMs). The ``UniversalLLMClient`` provides a unified interface for interacting with different LLM providers, and the ``LLMFactory`` makes it easy to configure and switch between them.

Out-of-the-box, Orkes includes support for:

- OpenAI-compatible APIs
- Anthropic's Claude
- Google's Gemini

You can also easily implement your own custom strategies to connect to any other LLM service or local model.

Agent and Tool Support
----------------------
While the graph-based architecture is the core of Orkes, it also provides support for building and using agents and tools. You can define custom tools using the ``OrkesToolSchema`` and use them within your graph's nodes to interact with external APIs, databases, or other services. This allows you to build sophisticated agent-like behaviors within the structured and controllable environment of an Orkes graph.