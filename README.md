<h2 align="center">
  <img width="17%" alt="Orkes logo" src="assets/orkes.png"><br/>
  No abstractions. No black boxes. Just Your Logic
</h2>
<p align="center">
  <a href="https://badge.fury.io/py/orkes">
    <img src="https://badge.fury.io/py/orkes.svg" alt="PyPI version">
  </a>
  <a href="https://opensource.org/licenses/MIT">
    <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License: MIT">
  </a>
  <a href="https://orkes.readthedocs.io/">
    <img src="https://img.shields.io/readthedocs/orkes?logo=read-the-docs&style=flat-square" alt="Docs">
  </a>
</p>

Orkes is a Python library for building, coordinating, and observing any complex workflow that can be represented as a graph. While it is well-suited for building LLM-powered agentic systems, its core focus is on providing a flexible and intuitive graph-based framework with an emphasis on explicit control flow, transparent logic, and comprehensive traceability.

## Core Concepts

At the heart of Orkes is a powerful graph-based architecture inspired by `NetworkX`. This design allows you to define your workflows as a graph of nodes and edges, where each node is a simple Python function.

-   **OrkesGraph**: The main canvas for your workflow. It holds the nodes and edges that define your application's logic.
-   **Stateful Execution**: A shared state object is passed between nodes, allowing for seamless data flow and management throughout the graph's execution.
-   **Graph Traceability**: Orkes provides a built-in traceability and visualization system. When you run a graph, Orkes can generate a detailed execution trace that can be visualized as an interactive HTML file, making it easy to debug and understand your workflows.

## Features

-   **Graph-based Architecture**: Define complex workflows as a graph of nodes and edges, with support for conditional branching and loops.
-   **Traceability and Visualization**: Generate interactive traces of your graph executions to visualize the flow of data and control.
-   **Pluggable LLM Integrations**: A flexible and extensible system for integrating with LLMs, with out-of-the-box support for OpenAI, Anthropic's Claude, and Google's Gemini.
-   **Agent and Tool Support**: Define custom tools and use them within your graph's nodes to interact with external APIs and services.
-   **Familiar Interface**: The graph-based interface is inspired by `NetworkX`, providing a familiar and powerful paradigm for those with experience in graph-based programming.

## Getting Started

Here's a simple example of how to build and run a graph with Orkes:

```python
from typing import TypedDict
from orkes.graph.core import OrkesGraph
from orkes.graph.runner import GraphRunner

# 1. Define the state
class GreetingState(TypedDict):
    name: str
    greeting: str

# 2. Create the graph and nodes
graph = OrkesGraph(GreetingState)

def greeter_node(state: GreetingState) -> GreetingState:
    state['greeting'] = f"Hello, {state['name']}!"
    return state

graph.add_node('greeter', greeter_node)

# 3. Connect the nodes with edges
graph.add_edge(graph.START, 'greeter')
graph.add_edge('greeter', graph.END)

# 4. Compile and run the graph
compiled_graph = graph.compile()
runner = GraphRunner(compiled_graph)
initial_state = GreetingState(name="World", greeting="")
final_state = runner.run(initial_state)

print(final_state)
# Expected output: {'name': 'World', 'greeting': 'Hello, World!'}

# 5. Visualize the trace
runner.visualize_trace("greeting_trace.html")
```

Here is an example how the orkes graph visualization will look like:

<h2 align="left">
  <img width="60%" alt="example" src="assets/inspector-example.png"><br/>
</h2>

## Roadmap

| Feature                  | Description                                                                                                     | Status  |
| ------------------------ | --------------------------------------------------------------------------------------------------------------- | ------- |
| Boilerplate Agent        | Provide a well-structured boilerplate for creating new agents to accelerate the development of agentic systems. | Planned |
| Parallel Graph Execution | Enhance the graph runner to support parallel execution of independent branches for improved performance.        | Planned |
| Tracer Web Platform      | Develop a standalone web-based platform for visualizing and inspecting graph traces in real-time.               | Planned |

## Documentation
For more details, visit our [Documentation Page](https://orkes.readthedocs.io/).

## Contributing
Contributions are welcome! Please see the [Contributing Guide](CONTRIBUTING.md) for more information.

## License
Orkes is licensed under the [MIT License](LICENSE).
