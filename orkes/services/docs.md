
# orkes.services

This documentation covers the three foundational components of the **LLM Core Layer**:

1. **Prompt Handler** — for structured prompt generation
2. **LLM Connection** — for model API communication
3. **Response Parser** — for handling streamed or batched outputs

Together, they form the base for building **LLM-driven agent pipelines** or **custom orchestration frameworks**.

## Table of Contents
1. [Architecture Overview](#architecture-overview)
2. [Prompt Handler](#prompt-handler)
3. [LLM Connection](#llm-connection)
4. [Response Parser](#response-parser)
5. [Usage Example](#usage-example)
6. [Future Extensions](#future-extensions)


## Architecture Overview

```
┌──────────────────────────────┐
│        Prompt Handler        │
│  (System/User Message Gen)   │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│       LLM Connection         │
│ (Send / Stream / HealthCheck)│
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│       Response Parser        │
│ (Parse Stream / Full Output) │
└──────────────────────────────┘
```

Each layer can be **independently extended** (e.g. adding support for OpenAI, Claude, or Mistral).


## Prompt Handler

### Overview

The **Prompt Handler** generates structured message payloads for chat-based LLMs, supporting **templated prompts** with runtime variable substitution.

Used to construct messages like:

```python
[
  {"role": "system", "content": "..."},
  {"role": "user", "content": "..."}
]
```
### Class Diagram

```
PromptInterface (ABC)
│
└── ChatPromptHandler
       ├── gen_messages(queries, chat_history)
       ├── _format_prompt(template, values)
       └── get_all_keys()
```


### `PromptInterface`

Abstract base class defining required prompt operations.

| Method                                     | Description                                     |
| ------------------------------------------ | ----------------------------------------------- |
| `gen_messages(queries, chat_history=None)` | Generate full chat message payloads             |
| `get_all_keys()`                           | Return expected placeholder keys from templates |

### `ChatPromptHandler`

Concrete implementation for **chat-based LLM prompts**.

| Parameter                | Type  | Description                    |
| ------------------------ | ----- | ------------------------------ |
| `system_prompt_template` | `str` | Template for the system prompt |
| `user_prompt_template`   | `str` | Template for the user prompt   |

**Example:**

```python
handler = ChatPromptHandler(
    system_prompt_template="{persona}. Respond concisely and helpfully.",
    user_prompt_template="{language}{input}"
)
```

**Generated messages:**

```python
queries = {
    "system": {"persona": "You are a support assistant."},
    "user": {"language": "English: ", "input": "Explain transformers briefly."}
}

messages = handler.gen_messages(queries)
```

Output:

```python
[
  {"role": "system", "content": "You are a support assistant. Respond concisely and helpfully."},
  {"role": "user", "content": "English: Explain transformers briefly."}
]
```

## LLM Connection

### Overview

Defines the **core communication layer** for interacting with model APIs (like OpenAI-compatible vLLM servers).

Supports:

* Sync message sending
* Async streaming
* Health checks
* Configurable generation parameters

---

### Class Diagram

```
LLMInterface (ABC)
│
└── vLLMConnection
      ├── send_message()
      ├── stream_message()
      └── health_check()
```

---

### `LLMInterface`

Abstract base defining required methods for all connection types.

| Method                    | Description               |
| ------------------------- | ------------------------- |
| `send_message(message)`   | Send synchronous requests |
| `stream_message(message)` | Async stream handling     |
| `health_check()`          | Server health validation  |

---

### `vLLMConnection`

Implementation for **vLLM REST API**.

| Parameter    | Type   | Description                 |
| ------------ | ------ | --------------------------- |
| `url`        | `str`  | Base URL of the LLM service |
| `model_name` | `str`  | Model identifier            |
| `headers`    | `dict` | Custom HTTP headers         |
| `api_key`    | `str`  | Optional API key            |

**Default settings:**

```python
{
  "temperature": 0.2,
  "top_p": 0.6,
  "frequency_penalty": 0.2,
  "presence_penalty": 0.0,
  "seed": 22
}
```

---

### Methods

#### `send_message(message, end_point="/v1/chat/completions", settings=None)`

Sends a synchronous POST request.

```python
resp = client.send_message(messages)
print(resp.json())
```

#### `async stream_message(message, end_point="/v1/chat/completions", settings=None)`

Streams incremental chunks.

```python
async for chunk in client.stream_message(messages):
    print(chunk)
```

#### `health_check(end_point="/health")`

Simple GET check.

```python
print(client.health_check().status_code)
```

---

## 📤 Response Parser

### Overview

Handles **streamed** and **non-streamed** model responses using flexible parser interfaces.

---

### Class Diagram

```
ResponseInterface (ABC)
│
├── ChatResponse
│     ├── parse_stream_response()
│     ├── parse_full_response()
│     └── _generate_event()
│
└── StreamResponseBuffer
      ├── stream()
      └── _is_buffer_full()
```

---

### `ResponseInterface`

Defines the parsing contract.

| Method                         | Description                             |
| ------------------------------ | --------------------------------------- |
| `parse_stream_response(chunk)` | Parse incremental streaming data        |
| `parse_full_response(payload)` | Parse entire payloads                   |
| `_generate_event(buffer)`      | Format buffered data into event strings |

---

### `ChatResponse`

Concrete implementation for **chat-style responses** (e.g. OpenAI/vLLM).

| Parameter   | Type  | Default   | Description             |
| ----------- | ----- | --------- | ----------------------- |
| `end_token` | `str` | `"<EOT>"` | Marks stream completion |

**Behavior:**

* Detects `[DONE]` or `end_token`
* Optionally returns **SSE** formatted events
* Graceful handling of malformed chunks

---

### `StreamResponseBuffer`

Buffers streaming responses and yields formatted chunks.

| Method                                   | Description                          |
| ---------------------------------------- | ------------------------------------ |
| `async stream(response, buffer_size=10)` | Yields parsed events as data arrives |
| `_is_buffer_full(buffer, size)`          | Determines when to flush buffer      |

**Example:**

```python
response = requests.get(url, stream=True)
parser = ChatResponse()
buffer = StreamResponseBuffer(parser)

async for event in buffer.stream(response):
    print(event)
```

---

## Usage Example

```python
from llm_connection import vLLMConnection
from prompt_handler import ChatPromptHandler
from response_parser import ChatResponse, StreamResponseBuffer

# Step 1: Build prompts
handler = ChatPromptHandler(
    system_prompt_template="{persona}.",
    user_prompt_template="{input}"
)

queries = {
    "system": {"persona": "You are a creative assistant."},
    "user": {"input": "Write a short haiku about autumn."}
}
messages = handler.gen_messages(queries)

# Step 2: Connect to model
client = vLLMConnection("http://localhost:8000", "mistral-7b")

# Step 3: Stream results
response = client.send_message(messages)
parser = ChatResponse()
print(parser.parse_full_response(response.json()))
```

## Future Extensions

| Feature             | Description                                                 |
| ------------------- | ----------------------------------------------------------- |
| Tool prompts        | Extend `PromptHandler` to include function calling contexts |
| Async HTTP          | Replace `requests` with `aiohttp` in `vLLMConnection`       |
| Unified errors      | Add standard error objects for failed responses             |
| Advanced buffering  | Sentence-aware or token-based stream flush                  |
| Template validation | Validate placeholders on initialization                     |
| Multi-turn chaining | Stateful prompt evolution across turns                      |
