# orkes.agents

This framework provides a **tool-enabled agent architecture** where an LLM agent can dynamically invoke **tools/actions** based on prompts and structured inputs.

It combines:

* **ActionBuilder** — Define callable tools with typed input schemas.
* **Agent** — Standard LLM agent interface with prompt handling and streaming.
* **ToolAgent** — LLM agent with access to multiple tools for dynamic execution.


## 📘 Table of Contents
1. [Overview](#overview)
2. [Core Classes](#core-classes)
   * [ActionBuilder](#actionbuilder)
   * [AgentInterface & Agent](#agentinterface--agent)
   * [ToolAgent](#toolagent)
3. [Usage Example](#usage-example)
4. [Validation & Safety](#validation--safety)
5. [Future Extensions](#future-extensions)


## Overview
* `ActionBuilder` lets you define **tools/functions** with:

  * Typed inputs via **Pydantic models**
  * JSON schema for LLM tool calls
  * Runtime validation and execution

* `Agent` connects an LLM and prompt handler to generate responses.

* `ToolAgent` wraps an LLM with a **set of callable tools**, parses LLM responses, and optionally executes tools automatically.

This enables **RAG workflows, reasoning pipelines, and multi-tool orchestration**.


## Core Classes
### `ActionBuilder`

Defines a callable tool with typed input parameters.

#### Initialization
```python
builder = ActionBuilder(
    func_name="search_tool",
    params={
        "query": {"type": str, "default": None, "desc": "Search query"},
        "limit": {"type": int, "default": 5, "desc": "Max results"}
    },
    description="Tool to perform a search",
    func=my_search_function
)
```

#### Key Methods
| Method                           | Description                                                  |
| -------------------------------- | ------------------------------------------------------------ |
| `get_model_class()`              | Returns the Pydantic model class for input validation.       |
| `get_schema_detail()`            | Returns detailed schema with descriptions.                   |
| `get_schema_tool(if_desc=False)` | Returns JSON schema compatible with LLM tool calling.        |
| `validate_params(data)`          | Validates input dict against schema, returns Pydantic model. |
| `execute(data)`                  | Validates input and calls the actual function.               |


### `AgentInterface` & `Agent`
`AgentInterface` is an abstract base class requiring `invoke()`.

```python
class Agent(AgentInterface):
    def __init__(self, name, prompt_handler, llm_connection, response_handler):
        ...
```

#### Methods
* `invoke(queries, chat_history=None)` — Generate LLM response.
* `stream(queries, chat_history=None, mode="default")` — Async streaming with parsing modes:

  * `default` — Parsed text
  * `raw` — Raw chunks
  * `sse` — Parsed as Server-Sent-Events


### `ToolAgent`
An LLM agent with **tools**.

#### Initialization
```python
agent = ToolAgent(name="ToolAgent", llm_connection=my_llm)
```

* `tools` — Dict of `ActionBuilder` instances
* `default_system_prompt` — Guides the LLM to call tools correctly
* `default_tools_wrapper` — Start/end tokens for tool JSON blocks

#### Methods
| Method                                                  | Description                                           |
| ------------------------------------------------------- | ----------------------------------------------------- |
| `add_tools(actions)`                                    | Register a list of `ActionBuilder` tools              |
| `_build_tools_prompt()`                                 | Generates full prompt including JSON schema for tools |
| `invoke(query, chat_history=None, execute_tools=False)` | Sends query to LLM, optionally executes tools         |
| `_parse_tool_response(response)`                        | Extracts tool calls from LLM JSON response            |

#### Tool Execution
* Supports **automatic execution** if `execute_tools=True`:

```python
results = agent.invoke("Find the latest news", execute_tools=True)
```

* Returns a dict mapping `tool_name` → result.

## Usage Example
```python
from orkes.agents.actions import ActionBuilder
from orkes.agents.core import ToolAgent

# Define a tool
def add_numbers(a: int, b: int) -> int:
    return a + b

adder = ActionBuilder(
    func_name="AddNumbers",
    params={
        "a": {"type": int, "desc": "First number"},
        "b": {"type": int, "desc": "Second number"}
    },
    description="Adds two numbers",
    func=add_numbers
)

# Initialize ToolAgent
agent = ToolAgent(name="MathAgent", llm_connection=my_llm)
agent.add_tools([adder])

# Invoke with tool execution
result = agent.invoke(
    query="Calculate 2 + 3",
    execute_tools=True
)

print(result)
# Output: {'AddNumbers': 5}
```

## Validation & Safety
* **ActionBuilder** enforces typed inputs via Pydantic.
* **Duplicate tools** are rejected.
* **LLM tool response parsing** normalizes JSON to `{function, parameters}`.
* Tool execution errors are captured per tool to prevent crashes.
* Tools can be executed safely or just listed by the LLM.

## Future Extensions
* Support **async tool execution**.
* Automatic **tool selection reasoning** using LLM outputs.
* Richer **tool metadata** (categories, constraints).
* Integrate with **OrkesGraph workflows** for multi-step orchestrations.
* Add **tool call logging** for audit and replay.

