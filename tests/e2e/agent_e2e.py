"""End-to-end check of an agent-style graph against a running Orkes Watcher.

The graph uses orkes's real LLM client (OpenAI-style) against a scripted mock
LLM started here, tools traced with @orkes_tracable, a parallel research step,
an agent <-> tools loop, a streamed final answer from an async node, and a
guardrail that can escalate. Each scenario is sent to the watcher, and the
trace is checked locally with a recording sink. Not collected by pytest:

    ORKES_WATCHER_KEY=<project ingest key> python tests/e2e/agent_e2e.py

ORKES_WATCHER_URL defaults to http://localhost:8000.

Graph:
    START -> classify -?-> plan ==> [search_web, search_kb] => merge -> agent
                      \\-> respond                                   agent -?-> tools -> agent
    agent -?-> respond -> guard -?-> END | escalate -> END
"""
import asyncio
import json
import logging
import os
import sys
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import List, TypedDict

from orkes.exporters import TraceSink
from orkes.exporters.watcher import WatcherSink
from orkes.graph.core import OrkesGraph
from orkes.graph.utils import orkes_tracable
from orkes.services.connectors import LLMFactory
from orkes.shared.schema import OrkesMessagesSchema

URL = os.environ.get("ORKES_WATCHER_URL", "http://localhost:8000")
KEY = os.environ.get("ORKES_WATCHER_KEY")


# --- Scripted mock LLM (OpenAI chat format) ---------------------------------------

def _user_text(messages):
    return next((m.get("content") or "" for m in messages if m.get("role") == "user"), "")


def _system_text(messages):
    return " ".join(m.get("content") or "" for m in messages if m.get("role") == "system")


def mock_reply(body):
    """What the scripted LLM says, given the request body."""
    messages = body["messages"]
    question = _user_text(messages).lower()
    system = _system_text(messages)

    if body.get("tools"):
        tool_results = sum(m.get("role") == "tool" for m in messages)
        if "loop forever" in question:
            calls = [("web_search", {"query": "again"})]
        elif tool_results == 0 and "divide" in question:
            calls = [("calculator", {"expression": "1/0"})]
        elif tool_results == 0:
            calls = [("get_weather", {"location": "Jakarta"}), ("web_search", {"query": question[:40]})]
        elif tool_results == 2:
            calls = [("calculator", {"expression": "21*2"})]
        else:
            return {"role": "assistant", "content": "Draft: it's sunny in Jakarta, and the answer is 42."}
        return {"role": "assistant", "content": None, "tool_calls": [
            {"id": f"call_{tool_results}_{i}", "type": "function",
             "function": {"name": name, "arguments": json.dumps(args)}}
            for i, (name, args) in enumerate(calls)
        ]}
    if "Classify" in system:
        route = "research" if any(w in question for w in ("compare", "weather", "research", "divide", "loop")) else "simple"
        return {"role": "assistant", "content": route}
    if "Summarize" in system:
        return {"role": "assistant", "content": "KB summary: orkes is a graph runtime."}
    return {"role": "assistant", "content": "Final answer: sunny in Jakarta; 21*2 = 42."}


class MockLLM(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        time.sleep(0.05)  # network latency
        reply = mock_reply(body)
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for word in (reply["content"] or "").split(" "):
                chunk = {"choices": [{"delta": {"content": word + " "}}]}
                self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
                self.wfile.flush()
                time.sleep(0.01)
            self.wfile.write(b"data: [DONE]\n\n")
            return
        data = json.dumps({"choices": [{"index": 0, "message": reply}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


# --- Tools ------------------------------------------------------------------------------

@orkes_tracable
def get_weather(location: str) -> str:
    """Get the current weather.

    Args:
        location (str): City name.
    """
    time.sleep(0.02)
    return f"Sunny, 31C in {location}"


@orkes_tracable
def web_search(query: str) -> str:
    """Search the web.

    Args:
        query (str): What to search for.
    """
    time.sleep(0.03)
    return f"3 results for '{query}'"


@orkes_tracable
def calculator(expression: str) -> str:
    """Evaluate an arithmetic expression.

    Args:
        expression (str): e.g. "21*2".
    """
    a, op, b = expression.partition("*") if "*" in expression else expression.partition("/")
    return str(int(a) * int(b) if op == "*" else int(a) / int(b))  # 1/0 raises


@orkes_tracable
def kb_lookup(topic: str) -> List[str]:
    return [f"doc about {topic}", "orkes overview"]


TOOLS = {"get_weather": get_weather, "web_search": web_search, "calculator": calculator}


# --- Graph ----------------------------------------------------------------------------

class AgentState(TypedDict):
    question: str
    route: str
    research: dict
    messages: list
    pending_calls: list
    tool_rounds: int
    answer: str
    escalated: bool


def build(llm, sinks, max_agent_passes=6):
    def classify(s: AgentState):
        reply = llm.send_message(OrkesMessagesSchema(messages=[
            {"role": "system", "content": "Classify the request as research or simple."},
            {"role": "user", "content": s["question"]},
        ]))
        s["route"] = reply["content"]["content"].strip()
        return s

    def plan(s: AgentState):
        return s

    def search_web(s: AgentState):
        s["research"] = {"web": web_search(s["question"])}
        return s

    def search_kb(s: AgentState):
        docs = kb_lookup("orkes")
        summary = llm.send_message(OrkesMessagesSchema(messages=[
            {"role": "system", "content": "Summarize these documents."},
            {"role": "user", "content": "\n".join(docs)},
        ]))
        s["research"] = {"kb": summary["content"]["content"]}
        return s

    def merge(s: AgentState, branch_results):
        s["research"] = {k: v for r in branch_results.values() for k, v in r["research"].items()}
        return s

    def agent(s: AgentState):
        if not s["messages"]:
            s["messages"] = [
                {"role": "system", "content": "You are a helpful agent. Use tools when needed."},
                {"role": "user", "content": s["question"]},
                {"role": "user", "content": f"Research notes: {json.dumps(s['research'])}"},
            ]
        reply = llm.send_message(OrkesMessagesSchema(messages=s["messages"]), tools=list(TOOLS.values()))["content"]
        if reply["content_type"] == "tool_calls":
            s["messages"] = s["messages"] + [{"role": "assistant", "content": reply["content"], "content_type": "tool_calls"}]
            s["pending_calls"] = reply["content"]
        else:
            s["messages"] = s["messages"] + [{"role": "assistant", "content": reply["content"]}]
            s["pending_calls"] = []
        return s

    def tools(s: AgentState):
        results = [
            {"role": "tool", "content": TOOLS[c["function_name"]](**c["arguments"]), "tool_call_id": c["id"]}
            for c in s["pending_calls"]
        ]
        s["messages"] = s["messages"] + results
        s["pending_calls"] = []
        s["tool_rounds"] += 1
        return s

    async def respond(s: AgentState):
        chunks = []
        stream = llm.stream_message(OrkesMessagesSchema(messages=[
            {"role": "system", "content": "Write the final answer for the user."},
            {"role": "user", "content": s["question"]},
        ]))
        async for chunk in stream:
            chunks.append(chunk)
        s["answer"] = "".join(chunks).strip()
        return s

    def guard(s: AgentState):
        return s

    def escalate(s: AgentState):
        s["escalated"] = True
        return s

    g = OrkesGraph(AgentState, name="e2e-agent", description="Agent with research branches, tools and a guardrail.", trace_sinks=sinks)
    for name, fn in [("classify", classify), ("plan", plan), ("search_web", search_web), ("search_kb", search_kb),
                     ("merge", merge), ("agent", agent), ("tools", tools), ("respond", respond),
                     ("guard", guard), ("escalate", escalate)]:
        g.add_node(name, fn)
    g.add_edge(g.START, "classify")
    g.add_conditional_edge("classify", lambda s: s["route"], {"research": "plan", "simple": "respond"})
    g.add_parallel_edges("plan", ["search_web", "search_kb"], "merge")
    g.add_edge("search_web", "merge")
    g.add_edge("search_kb", "merge")
    g.add_edge("merge", "agent")
    g.add_conditional_edge("agent", lambda s: "tools" if s["pending_calls"] else "answer",
                           {"tools": "tools", "answer": "respond"}, max_passes=max_agent_passes)
    g.add_edge("tools", "agent", max_passes=max_agent_passes)
    g.add_edge("respond", "guard")
    g.add_conditional_edge("guard", lambda s: "escalate" if "refund" in s["question"].lower() else "ok",
                           {"ok": "END", "escalate": "escalate"})
    g.add_edge("escalate", g.END)
    return g.compile()


# --- Local checks ---------------------------------------------------------------------

class Recorder(TraceSink):
    """Keeps what the watcher was sent, to check it locally."""

    def __init__(self):
        self.edges, self.end = [], None

    def on_run_start(self, trace):
        self.edges, self.end = [], None

    def on_edge(self, edge_trace):
        self.edges.append(edge_trace)

    def on_run_end(self, trace):
        self.end = trace


class WarningCounter(logging.Handler):
    def __init__(self):
        super().__init__(logging.WARNING)
        self.records = []

    def emit(self, record):
        self.records.append(record)


def summarize(rec):
    ids = Counter(e.edge_id for e in rec.edges)
    return {
        "status": rec.end.status,
        "edges": len(rec.edges),
        "loops": sum(n - 1 for n in ids.values()),
        "function_traces": sum(len(e.function_traces) for e in rec.edges),
        "llm_traces": sum(len(e.llm_traces) for e in rec.edges),
        "streamed": any(str(t.parsed_response.content).startswith("Final answer") for e in rec.edges for t in e.llm_traces),
        "parallel": any(isinstance(e.to_node, list) for e in rec.edges),
        "failed_node": rec.end.failed_node,
        "error": (rec.end.error or "").split("\n")[0],
    }


SCENARIOS = [
    # (label, question, max agent passes, expected)
    # loops = repeat passes over the same edge (the watcher's definition): with two
    # tool rounds, agent's edge runs 3 times (2 repeats) and tools->agent twice (1).
    ("research + 2 tool rounds", "Compare the weather in Jakarta and compute 21*2", 6,
     {"status": "FINISHED", "loops": 3, "parallel": True, "streamed": True, "llm_traces": 6, "function_traces": 5}),
    ("simple question", "Hi there", 6,
     {"status": "FINISHED", "loops": 0, "parallel": False, "streamed": True, "llm_traces": 2}),
    ("guardrail escalates", "Research a refund for my weather order", 6,
     {"status": "FINISHED", "loops": 3, "parallel": True, "streamed": True}),
    ("tool raises", "Please divide something", 6,
     {"status": "FAILED", "failed_node": "tools", "error": "ZeroDivisionError: division by zero"}),
    ("runaway agent hits max_passes", "Please loop forever", 3,
     {"status": "FAILED", "failed_node": "agent", "error": "RuntimeError: The conditional edge from 'agent' was traversed more than its max_passes limit of 3 without reaching a stop condition. Check the loop's exit condition, or raise max_passes if it needs more passes."}),
]


def main():
    if not KEY:
        sys.exit("Set ORKES_WATCHER_KEY to a project ingest key (see the watcher's Keys page).")

    server = ThreadingHTTPServer(("127.0.0.1", 0), MockLLM)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    llm = LLMFactory.create_vllm(url=f"http://127.0.0.1:{server.server_address[1]}/v1", model="mock-agent")

    warnings = WarningCounter()
    logging.getLogger("orkes").addHandler(warnings)

    recorder = Recorder()
    sink = WatcherSink(KEY, URL)
    print(f"Sending to {URL}\n")
    failures = 0
    for label, question, max_passes, expected in SCENARIOS:
        runner = build(llm, [recorder, sink], max_passes)
        state = {"question": question, "route": "", "research": {}, "messages": [], "pending_calls": [],
                 "tool_rounds": 0, "answer": "", "escalated": False}
        start = time.perf_counter()
        try:
            asyncio.run(runner.arun(state))
        except (ZeroDivisionError, RuntimeError):
            pass
        took = time.perf_counter() - start
        got = summarize(recorder)
        bad = {k: (v, got[k]) for k, v in expected.items() if got[k] != v}
        failures += bool(bad)
        print(f"{'PASS' if not bad else 'FAIL'}  {label:<32} run {runner.run_id}  ({took:.2f}s)")
        print(f"      {got}")
        for k, (want, have) in bad.items():
            print(f"      expected {k}={want!r}, got {have!r}")

    rejected = [r.getMessage() for r in warnings.records]
    print(f"\nwatcher rejections / send warnings: {len(rejected)}")
    for message in rejected:
        print("  ", message[:300])
    server.shutdown()
    sys.exit(1 if failures or rejected else 0)


if __name__ == "__main__":
    main()
