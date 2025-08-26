# Orkes

## 🔍 What is Orkes?

**Orkes** helps you coordinate LLM agents using plain Python.
No magic, no unnecessary layers. Just **explicit control flow**, **transparent agent logic**, and **simple message passing**.

## 📝 Background

A while back, I was tasked with ensuring that our agentic-based streaming calls closed properly when a client disconnected.

Out of the box, there wasn’t a straightforward way to close the underlying HTTP connection. Why does this matter?

Because in our case, leaving connections hanging was detrimental to keeping our self-hosted LLM stable and reliable.

The frustrating part: today’s higher level libraries are abstractions on top of abstractions, hidden under even more abstractions, and at the end hidden in dependencies abstraction, layered until a simple fix turns into a complete clusterfuck.

Hence the pain of using high-level abstraction frameworks, some niche cases just don’t get covered.


## 🔹 Core Principles

* **Explicit control flow** — use DAGs, FSMs, or plain loops
* **Transparent agents** — define prompt, tool, and logic directly
* **Simple message passing** — plain dicts, no graph state magic
* **Minimal dependencies** — only what you truly need
* **100% Pythonic** — easy to read, modify, and extend
* **Stateless by default** — you control memory and state
* **Hackable and debuggable** — nothing hidden

## 🛠️ Project Status

This is the initial stage of Orkes.

* [x] Vision and core philosophy
* [ ] Basic orchestration engine
* [ ] Agent structure (prompt + tool + fn)
* [ ] Minimal examples
* [ ] Optional visualizer (planned)

## License

This poject is available as open source under the terms of the [MIT License](https://github.com/hfahrudin/orkes/blob/main/LICENSE).

