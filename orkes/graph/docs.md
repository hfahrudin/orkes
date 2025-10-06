
# orkes.graph

`OrkesGraph` provides a **graph-based orchestration layer** for connecting and running computational nodes (functions) with conditional and forward edges. It is designed to integrate with **typed state dictionaries** and agent workflows. `GraphRunner` executes compiled graphs in a safe and structured way.

---

## 📘 Table of Contents

1. [Overview](#overview)
2. [Class Diagram](#class-diagram)
3. [Core Concepts](#core-concepts)
4. [Classes](#classes)

   * [OrkesGraph](#orkesgraph)
   * [GraphRunner](#graphrunner)
5. [Usage Example](#usage-example)
6. [Validation & Safety](#validation--safety)
7. [TODO / Future Extensions](#todo--future-extensions)

---

## 🧩 Overview

`OrkesGraph` is a **directed graph orchestrator** for function nodes:

* Nodes represent **functions** operating on a **typed state dictionary**.
* Edges connect nodes, representing **forward execution** or **conditional branching**.
* The graph ensures **start and end integrity** and supports **loop detection**.
* Designed for **agent orchestration**, workflow pipelines, or RAG/LLM orchestration.
* `GraphRunner` executes a compiled graph, applying node functions sequentially while maintaining state integrity.

---

## 🧱 Class Diagram

```
OrkesGraph
├── add_node(name, func)
├── add_edge(from_node, to_node, max_passes)
├── add_conditional_edge(from_node, gate_function, condition, max_passes)
├── compile() -> GraphRunner
├── detect_loop() -> bool
├── _validate_from_node(from_node)
├── _validate_to_node(to_node)
└── _validate_condition(condition)

GraphRunner
├── run(invoke_state: Dict) -> Dict
```

---

## 🧠 Core Concepts

| Concept            | Description                                                             |
| ------------------ | ----------------------------------------------------------------------- |
| Node               | Computational unit (function) with typed input/output state.            |
| Edge               | Connects nodes; can be **ForwardEdge** or **ConditionalEdge**.          |
| START / END Nodes  | Special nodes marking beginning and termination of the workflow.        |
| Graph State        | TypedDict defining the state structure passed between nodes.            |
| Node Pool          | Registry of all nodes in the graph.                                     |
| Edge Pool          | Registry of all edges in the graph.                                     |
| Conditional Branch | Allows branching execution depending on a gate function and conditions. |

---

## 🏗️ Classes

### `OrkesGraph`

Graph orchestrator managing nodes, edges, and execution flow.

#### Initialization

```python
graph = OrkesGraph(state=MyTypedState)
```

| Parameter | Type        | Description                            |
| --------- | ----------- | -------------------------------------- |
| `state`   | `TypedDict` | State schema shared between all nodes. |

**Raises:** `TypeError` if `state` is not a TypedDict class.

---

#### Key Methods

##### `add_node(name: str, func: Callable)`

Add a function node to the graph. Validates function signature and uniqueness.

##### `add_edge(from_node, to_node, max_passes: int = 25)`

Connect nodes with a **forward edge**. `from_node` can be a node name or `_StartNode`; `to_node` can be a node name or `_EndNode`.

##### `add_conditional_edge(from_node, gate_function, condition, max_passes: int = 25)`

Add a **conditional branch** with a gate function that selects edges based on state.

##### `compile() -> GraphRunner`

Finalize the graph:

* Checks start/end integrity.
* Ensures every node has an outgoing edge.
* Freezes the graph to prevent modification.
* Returns a `GraphRunner` object.

##### `detect_loop() -> bool`

Detect cycles in the graph. Returns `True` if a loop exists.

##### `_validate_from_node(from_node)`, `_validate_to_node(to_node)`, `_validate_condition(condition)`

Internal validation methods for nodes and conditional branches.

---

### `GraphRunner`

Executes a compiled `OrkesGraph` workflow by traversing nodes and applying their functions to the **typed state dictionary**.

#### Initialization

```python
runner = GraphRunner(nodes_pool=nodes_pool, graph_type=MyTypedState)
```

| Parameter    | Type                      | Description                                      |
| ------------ | ------------------------- | ------------------------------------------------ |
| `nodes_pool` | `Dict[str, NodePoolItem]` | Dictionary of all graph nodes (from OrkesGraph). |
| `graph_type` | `TypedDict`               | TypedDict class defining the graph state schema. |

**Attributes:** `graph_state`, `nodes_pool`, `state_def`

---

#### Methods

##### `run(invoke_state: Dict) -> Dict`

Executes the graph starting from the `START` node.

**Parameters:** `invoke_state` — Initial state values matching the graph’s TypedDict.

**Returns:** Updated graph state after traversing nodes along forward and conditional edges.

**Behavior:**

1. Validates keys in `invoke_state`.
2. Copies input state to avoid in-place mutation.
3. Traverses nodes from `START`.
4. Applies node functions sequentially.
5. Returns the updated state.

**Example:**

```python
from mygraph import OrkesGraph, GraphRunner
from mytypes import MyState

graph = OrkesGraph(state=MyState)

def add_greeting(state: MyState):
    state['message'] = "Hello"
    return state

graph.add_node("GreetNode", add_greeting)
graph.add_edge("START", "GreetNode")
graph.add_edge("GreetNode", "END")

runner = graph.compile()
initial_state = {"message": ""}
final_state = runner.run(initial_state)
print(final_state)
# Output: {'message': 'Hello'}
```

---

## ✅ Validation & Safety

* Nodes must be unique.
* Edges cannot be reassigned.
* Conditional edges must reference valid nodes.
* Graph must have a start and end assigned.
* Loops can be detected using `detect_loop()`.
* Graph is **immutable** after compilation.
* `run()` avoids mutating input state and validates keys.

---

## 🚧 TODO / Future Extensions

* Safer `_EndNode` handling.
* Fallback edges for conditional nodes.
* Advanced loop detection for nested/conditional graphs.
* Graph visualization support.
* Integration with **Orkes AgentInterface** for automated execution pipelines.

