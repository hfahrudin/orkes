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


## Getting Started

You can install the latest stable version of the Orkes using pip:

```cli
pip install orkes
```

<details><summary>Here's a simple example of how to build and run a graph with Orkes:</summary>

```Python

from orkes.graph.core import OrkesGraph
from typing import TypedDict, List

class SearchState(TypedDict):
    user_query: str
    search_queries: List[str]
    current_index: int
    raw_results: List[str]
    is_finished: bool

def planner_node(state: SearchState):
    # Mock planning logic
    state['search_queries'] = [f"Query {i+1}" for i in range(3)]
    state['current_index'] = 0
    return state

def search_node(state: SearchState):
    idx = state['current_index']
    state['raw_results'].append(f"Result for {state['search_queries'][idx]}")
    state['current_index'] += 1
    state['is_finished'] = state['current_index'] >= len(state['search_queries'])
    return state

def synthesis_node(state: SearchState):
    print(f"Final Output: {', '.join(state['raw_results'])}")
    return state

# Graph Construction
graph = OrkesGraph(SearchState)
graph.add_node('planner', planner_node)
graph.add_node('search', search_node)
graph.add_node('synthesizer', synthesis_node)

graph.add_edge(graph.START, 'planner')
graph.add_edge('planner', 'search')
graph.add_conditional_edge('search', 
    lambda s: 'end' if s['is_finished'] else 'loop',
    {'loop': 'search', 'end': 'synthesizer'}
)
graph.add_edge('synthesizer', graph.END)

# Execution
runner = graph.compile()
runner.run({"user_query": "Orkes vs Temporal", "current_index": 0, "raw_results": []})
```
</details>

<details><summary>Here is an example how the orkes graph visualization will look like:</summary>
<h2 align="center">
  <img width="60%" alt="example" src="assets/inspector-example.png"><br/>
</h2>
</details>

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


## Benchmarks

Orkes has been benchmarked against LangGraph on simple graph structures, demonstrating performance advantages. In direct comparisons of graphs with identical nodes and edges, Orkes consistently outperforms LangGraph in both latency and memory utilization.

### Key Findings

*   For a simple graph comprising 5 nodes, Orkes exhibits up to a 5x increase in speed and consumes up to 2x less memory compared to LangGraph.
*   When scaled to a 10-node graph, Orkes's performance gap widens, achieving up to 10x faster execution and using up to 3x less memory than LangGraph.

These preliminary results suggest Orkes can offer a more efficient and performant solution for developing and deploying LLM applications, particularly in scenarios involving graph-based workflows.

### Results

Example Benchmark Results (*values may vary*):

<details><summary>Basic Benchmark Results</summary>
<h2 align="center">
  <img width="80%" alt="Basic Benchmark Results" src="assets/benchmarks/basic_benchmark_results.png"><br/>
</h2>
</details>

<details><summary>Statebloat Benchmark Results</summary>
<h2 align="center">
  <img width="80%" alt="Statebloat Benchmark Results" src="assets/benchmarks/statebloat_benchmark_results.png"><br/>
</h2>
</details>

To replicate or run the benchmarks, navigate to the `tests/benchmarks` directory and execute the `run_all_benchmarks.py` script:

```bash
python tests/benchmarks/run_all_benchmarks.py
```

## Roadmap

| Feature                  | Description                                                                                                     | Status  |
| ------------------------ | --------------------------------------------------------------------------------------------------------------- | ------- |
| Boilerplate Agent        | Provide a well-structured boilerplate for creating new agents to accelerate the development of agentic systems. | Planned |
| Parallel Graph Execution | Enhance the graph runner to support parallel execution of independent branches for improved performance.        | Implemented |
| Tracer Web Platform      | Develop a standalone web-based platform for visualizing and inspecting graph traces in real-time.               | Progressing |

## Documentation
For more details, visit our [Documentation Page](https://orkes.readthedocs.io/).

## Contributing
Contributions are welcome! Please see the [Contributing Guide](CONTRIBUTING.md) for more information.

## License
Orkes is licensed under the [MIT License](LICENSE).
