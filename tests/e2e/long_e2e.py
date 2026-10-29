"""Long, multi-process stress run of a market-research agent against Orkes Watcher.

The story: a business team asks questions like "Should we launch electric scooter
rentals in Jakarta?". For each question, an agent researches four areas in
parallel, writes a report, has it reviewed until it's good enough, and sends
it to a human if there's a compliance risk. LLM replies come from a scripted
mock (started here) through orkes's real LLM client, so runs are repeatable.

    START
      -> receive_request -> understand_request -> plan_research
      ==> research_market_size | research_competitors | research_regulations | research_customer_sentiment
            each area:  research_<area>
                          ==> <area>_news_search | <area>_industry_reports | <area>_social_listening
                          => <area>_sources_combined
                          -> <area>_analyst -?-> <area>_analyst_tools -> <area>_analyst   (tool-calling loop)
                                           \\-?-> <area>_findings_ready
      => combine_research -> write_draft
      -> review_draft -?-> revise_draft -> review_draft                                   (until score >= 9)
                      \\-?-> write_final_report (streamed) -> compliance_check
      -?-> END | escalate_to_human -> END

One run takes about 70 s. Several OS processes run at once, each answering two
questions in parallel threads with one WatcherSink. Questions about Medan hit a
government-registry outage during regulation research, so those runs fail. One
more process is killed mid-run; the watcher should later mark it abandoned.
Each run's trace is checked locally, and the requests sent to the watcher are
counted to confirm data streams in while the run is still going.
Not collected by pytest:

    ORKES_WATCHER_KEY=<project ingest key> python tests/e2e/long_e2e.py

Options (env): ORKES_WATCHER_URL (default http://localhost:8000).
"""
import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TypedDict

URL = os.environ.get("ORKES_WATCHER_URL", "http://localhost:8000")
KEY = os.environ.get("ORKES_WATCHER_KEY")

AREAS = ["market_size", "competitors", "regulations", "customer_sentiment"]
SOURCES = ["news_search", "industry_reports", "social_listening"]
ANALYST_ROUNDS = 3  # tool-calling rounds per research area
REVISIONS = 2  # the reviewer scores 5, 7, then 9 (good enough)

SOURCE_SECONDS = 3.5
TOOL_SECONDS = 0.75
LLM_SECONDS = 0.3

# Each process answers two of these at once. Medan's regulation research hits
# a registry outage, so those runs fail.
PROCESS_REQUESTS = [
    ["Should we launch electric scooter rentals in Jakarta?",
     "Should we open a plant-based coffee chain in Bandung?"],
    ["Should we launch payroll software for small businesses in Surabaya?",
     "Should we start cold-chain grocery delivery in Makassar?"],
    ["Should we open co-working spaces for remote workers in Yogyakarta?",
     "Should we launch a pet-care booking app in Semarang?"],
    ["Should we launch motorbike ride-sharing in Medan?",
     "Should we open a used-car marketplace in Medan?"],
]
KILLED_REQUEST = "Should we launch late-night food delivery in Denpasar?"
OUTAGE_CITIES = {"Medan"}

# What each area's analyst asks its tools for, round by round.
ANALYST_PLANS = {
    "market_size": [
        [("lookup_statistics", {"metric": "monthly active users of similar services"}),
         ("search_web", {"query": "{product} market size {city}"})],
        [("lookup_statistics", {"metric": "average spend per customer"}),
         ("search_web", {"query": "{product} growth forecast Indonesia"})],
        [("lookup_statistics", {"metric": "urban population aged 18-40"}),
         ("search_web", {"query": "{product} adoption rate {city}"})],
    ],
    "competitors": [
        [("fetch_competitor_pricing", {"company": "the market leader"}),
         ("search_web", {"query": "top {product} providers in {city}"})],
        [("fetch_competitor_pricing", {"company": "the fastest-growing challenger"}),
         ("search_web", {"query": "{product} startups funding 2026"})],
        [("fetch_competitor_pricing", {"company": "the cheapest option"}),
         ("search_web", {"query": "{product} customer complaints {city}"})],
    ],
    "regulations": [
        [("check_regulation", {"topic": "business licensing"}),
         ("search_web", {"query": "{product} regulation {city}"})],
        [("fetch_government_registry", {"record": "required permits"}),
         ("check_regulation", {"topic": "consumer protection"})],
        [("check_regulation", {"topic": "data privacy"}),
         ("search_web", {"query": "{product} tax rules Indonesia"})],
    ],
    "customer_sentiment": [
        [("search_web", {"query": "{product} reviews {city}"}),
         ("lookup_statistics", {"metric": "app store rating of competitors"})],
        [("search_web", {"query": "what people dislike about {product}"}),
         ("lookup_statistics", {"metric": "willingness to pay survey"})],
        [("search_web", {"query": "{product} social media mentions {city}"}),
         ("lookup_statistics", {"metric": "net promoter score in the category"})],
    ],
}

AREA_FINDINGS = {
    "market_size": "Roughly 1.2M potential customers; the market grows about 18% a year.",
    "competitors": "Three established players; the leader charges about 20% above the cheapest option.",
    "regulations": "A special operating permit is required, and approval takes about 3 months.",
    "customer_sentiment": "Customers like the convenience but complain about reliability.",
}

REVIEW_FEEDBACK = {
    0: "Score: 5/10. The draft has no pricing comparison and no launch timeline.",
    1: "Score: 7/10. Pricing is covered; the permit risk needs a mitigation plan.",
    2: "Score: 9/10. Clear recommendation with risks and a timeline. Ready to send.",
}


def parse_request(text):
    product, city = re.search(r"(?:launch|open|start) (.+) in (\w+)\?", text).groups()
    return product, city


# --- Scripted mock LLM (OpenAI chat format) -----------------------------------------

def mock_reply(body):
    messages = body["messages"]
    system = " ".join(m.get("content") or "" for m in messages if m.get("role") == "system")
    question = next((m.get("content") or "" for m in messages if m.get("role") == "user"), "")
    product, city = parse_request(question) if "?" in question else ("the product", "the city")

    analyst = re.search(r"You are the (\w+) analyst", system)
    if analyst and body.get("tools"):
        area = analyst.group(1)
        rounds_done = sum(m.get("role") == "tool" for m in messages) // 2
        if rounds_done >= ANALYST_ROUNDS:
            return {"role": "assistant", "content": AREA_FINDINGS[area]}
        calls = ANALYST_PLANS[area][rounds_done]
        if area == "regulations" and city not in OUTAGE_CITIES:
            calls = [("check_regulation", {"topic": "required permits"}) if name == "fetch_government_registry"
                     else (name, args) for name, args in calls]
        return {"role": "assistant", "content": None, "tool_calls": [
            {"id": f"call_{area}_{rounds_done}_{i}", "type": "function",
             "function": {"name": name, "arguments": json.dumps(
                 {k: v.format(product=product, city=city) for k, v in args.items()})}}
            for i, (name, args) in enumerate(calls)
        ]}
    if "You receive business questions" in system:
        return {"role": "assistant", "content": f"Goal: decide whether to launch {product} in {city}, "
                                                f"with a go/no-go recommendation and the main risks."}
    if "You plan research" in system:
        return {"role": "assistant", "content": "Research plan: market size, competitors, regulations, "
                                                "customer sentiment."}
    if "You write reports" in system:
        return {"role": "assistant", "content": f"Draft: {product} in {city} looks promising, but needs a permit."}
    if "You review reports" in system:
        revision = int(re.search(r"Revision (\d+)", question).group(1))
        return {"role": "assistant", "content": REVIEW_FEEDBACK[min(revision, 2)]}
    if "You edit reports" in system:
        return {"role": "assistant", "content": "Revised draft that addresses the reviewer's feedback."}
    return {"role": "assistant", "content": f"Recommendation: launch {product} in {city} in two phases, "
                                            f"starting once the operating permit is approved."}


class MockLLM(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        time.sleep(LLM_SECONDS)
        reply = mock_reply(body)
        if body.get("stream"):
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.end_headers()
            for word in reply["content"].split(" "):
                self.wfile.write(f"data: {json.dumps({'choices': [{'delta': {'content': word + ' '}}]})}\n\n".encode())
                self.wfile.flush()
                time.sleep(0.05)
            self.wfile.write(b"data: [DONE]\n\n")
            return
        data = json.dumps({"choices": [{"index": 0, "message": reply}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


# --- Worker process: builds and runs the agent ----------------------------------------

def worker(llm_url: str, requests: list) -> None:
    from orkes.exporters import TraceSink
    from orkes.exporters.watcher import WatcherSink
    from orkes.graph.core import OrkesGraph
    from orkes.graph.utils import orkes_tracable
    from orkes.services.connectors import LLMFactory
    from orkes.shared.schema import OrkesMessagesSchema

    llm = LLMFactory.create_vllm(url=llm_url, model="mock-research-agent")

    # Tools (each call is recorded in the trace by @orkes_tracable)

    @orkes_tracable
    def search_sources(source: str, topic: str) -> list:
        time.sleep(SOURCE_SECONDS)
        return [f"{source}: 3 recent items about {topic}"]

    @orkes_tracable
    def search_web(query: str) -> str:
        """Search the web.

        Args:
            query (str): What to search for.
        """
        time.sleep(TOOL_SECONDS)
        return f"Top results for '{query}': 3 articles, 1 industry report."

    @orkes_tracable
    def lookup_statistics(metric: str) -> str:
        """Look up a statistic from the internal data warehouse.

        Args:
            metric (str): The statistic to look up.
        """
        time.sleep(TOOL_SECONDS)
        return f"{metric}: 42% (2026 survey, n=1,800)"

    @orkes_tracable
    def fetch_competitor_pricing(company: str) -> str:
        """Fetch a competitor's public prices.

        Args:
            company (str): Which competitor.
        """
        time.sleep(TOOL_SECONDS)
        return f"Pricing for {company}: IDR 15,000-25,000 per order"

    @orkes_tracable
    def check_regulation(topic: str) -> str:
        """Check the rules for a topic.

        Args:
            topic (str): The regulation topic.
        """
        time.sleep(TOOL_SECONDS)
        return f"{topic}: a special operating permit is required"

    @orkes_tracable
    def fetch_government_registry(record: str) -> str:
        """Fetch a record from the government business registry.

        Args:
            record (str): The record to fetch.
        """
        time.sleep(TOOL_SECONDS)
        raise ConnectionError("government business registry timed out after 30s")

    tools = {f.__name__: f for f in (search_web, lookup_statistics, fetch_competitor_pricing,
                                     check_regulation, fetch_government_registry)}

    class ResearchState(TypedDict):
        request: str
        goal: str
        research_plan: str
        area: str
        sources: dict
        findings: dict
        messages: list
        pending_tool_calls: list
        draft: str
        review_score: int
        review_feedback: str
        revision: int
        report: str
        needs_human: bool

    def ask(system, user):
        return llm.send_message(OrkesMessagesSchema(messages=[
            {"role": "system", "content": system}, {"role": "user", "content": user}]))["content"]["content"]

    def build(sinks):
        g = OrkesGraph(ResearchState, name="market-research-agent",
                       description="Researches a business question in four areas, writes a reviewed report, "
                                   "and escalates compliance risks to a human.",
                       trace_sinks=sinks)

        def receive_request(s: ResearchState):
            """Takes in the business question."""
            return s

        def understand_request(s: ResearchState):
            """Turns the question into a clear goal."""
            s["goal"] = ask("You receive business questions and state the goal.", s["request"])
            return s

        def plan_research(s: ResearchState):
            """Decides which areas to research."""
            s["research_plan"] = ask("You plan research for a business decision.", s["goal"])
            return s

        def combine_research(s: ResearchState, branch_results):
            """Collects the findings of all four research areas."""
            s["findings"] = {k: v for r in branch_results.values() for k, v in r["findings"].items()}
            return s

        def write_draft(s: ResearchState):
            """Writes the first draft of the report."""
            s["draft"] = ask("You write reports from research findings.", json.dumps(s["findings"]))
            return s

        def review_draft(s: ResearchState):
            """A reviewer scores the draft and gives feedback."""
            feedback = ask("You review reports and score them out of 10.",
                           f"Revision {s['revision']} of the report on: {s['request']}")
            s["review_feedback"] = feedback
            s["review_score"] = int(re.search(r"Score: (\d+)/10", feedback).group(1))
            return s

        def revise_draft(s: ResearchState):
            """Rewrites the draft to address the reviewer's feedback."""
            s["draft"] = ask("You edit reports based on reviewer feedback.", s["review_feedback"])
            s["revision"] += 1
            return s

        async def write_final_report(s: ResearchState):
            """Streams the final report."""
            chunks = []
            async for chunk in llm.stream_message(OrkesMessagesSchema(messages=[
                    {"role": "system", "content": "You write the final recommendation."},
                    {"role": "user", "content": s["request"]}])):
                chunks.append(chunk)
            s["report"] = "".join(chunks).strip()
            return s

        def compliance_check(s: ResearchState):
            """Flags reports that depend on a permit for human review."""
            s["needs_human"] = "permit" in s["report"].lower()
            return s

        def escalate_to_human(s: ResearchState):
            """Sends the report to a person to approve."""
            return s

        for fn in (receive_request, understand_request, plan_research, combine_research, write_draft,
                   review_draft, revise_draft, write_final_report, compliance_check, escalate_to_human):
            g.add_node(fn.__name__, fn)

        for area in AREAS:
            def start_area(s: ResearchState, area=area):
                s["area"] = area
                s["findings"] = {}
                return s

            def combine_sources(s: ResearchState, branch_results):
                s["sources"] = {k: v for r in branch_results.values() for k, v in r["sources"].items()}
                return s

            def analyst(s: ResearchState, area=area):
                if not s["messages"]:
                    s["messages"] = [
                        {"role": "system", "content": f"You are the {area} analyst. Use tools to research, "
                                                      f"then summarize what you found."},
                        {"role": "user", "content": s["request"]},
                        {"role": "user", "content": f"Sources so far: {json.dumps(s['sources'])}"},
                    ]
                reply = llm.send_message(OrkesMessagesSchema(messages=s["messages"]),
                                         tools=list(tools.values()))["content"]
                if reply["content_type"] == "tool_calls":
                    s["messages"] = s["messages"] + [{"role": "assistant", "content": reply["content"],
                                                      "content_type": "tool_calls"}]
                    s["pending_tool_calls"] = reply["content"]
                else:
                    s["findings"] = {area: reply["content"]}
                    s["pending_tool_calls"] = []
                return s

            def run_analyst_tools(s: ResearchState):
                s["messages"] = s["messages"] + [
                    {"role": "tool", "content": str(tools[c["function_name"]](**c["arguments"])),
                     "tool_call_id": c["id"]}
                    for c in s["pending_tool_calls"]
                ]
                s["pending_tool_calls"] = []
                return s

            def findings_ready(s: ResearchState):
                return s

            g.add_node(f"research_{area}", start_area)
            g.add_node(f"{area}_sources_combined", combine_sources)
            g.add_node(f"{area}_analyst", analyst)
            g.add_node(f"{area}_analyst_tools", run_analyst_tools)
            g.add_node(f"{area}_findings_ready", findings_ready)
            for source in SOURCES:
                def gather(s: ResearchState, source=source):
                    s["sources"] = {source: search_sources(source, f"{s['area']} for: {s['request']}")}
                    return s
                g.add_node(f"{area}_{source}", gather)

        g.add_edge(g.START, "receive_request")
        g.add_edge("receive_request", "understand_request")
        g.add_edge("understand_request", "plan_research")
        g.add_parallel_edges("plan_research", [f"research_{a}" for a in AREAS], "combine_research")
        for area in AREAS:
            gatherers = [f"{area}_{source}" for source in SOURCES]
            g.add_parallel_edges(f"research_{area}", gatherers, f"{area}_sources_combined")
            for name in gatherers:
                g.add_edge(name, f"{area}_sources_combined")
            g.add_edge(f"{area}_sources_combined", f"{area}_analyst")
            g.add_conditional_edge(f"{area}_analyst",
                                   lambda s: "use tools" if s["pending_tool_calls"] else "done",
                                   {"use tools": f"{area}_analyst_tools", "done": f"{area}_findings_ready"})
            g.add_edge(f"{area}_analyst_tools", f"{area}_analyst")
            g.add_edge(f"{area}_findings_ready", "combine_research")
        g.add_edge("combine_research", "write_draft")
        g.add_edge("write_draft", "review_draft")
        g.add_conditional_edge("review_draft",
                               lambda s: "approved" if s["review_score"] >= 9 else "needs changes",
                               {"approved": "write_final_report", "needs changes": "revise_draft"})
        g.add_edge("revise_draft", "review_draft")
        g.add_edge("write_final_report", "compliance_check")
        g.add_conditional_edge("compliance_check",
                               lambda s: "needs human" if s["needs_human"] else "ok",
                               {"needs human": "escalate_to_human", "ok": "END"})
        g.add_edge("escalate_to_human", g.END)
        return g.compile()

    class Recorder(TraceSink):
        def __init__(self):
            self.edges, self.end = [], None

        def on_edge(self, edge_trace):
            self.edges.append(edge_trace)

        def on_run_end(self, trace):
            self.end = trace

    class CountingSink(WatcherSink):
        """WatcherSink that also records when each request was sent (test only)."""

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.sent = Counter()
            self.times = {}

        def _post(self, session, run, body):
            self.sent[run.run_id] += 1
            self.times.setdefault(run.run_id, []).append(time.time())
            super()._post(session, run, body)

    warnings = []
    handler = logging.Handler(logging.WARNING)
    handler.emit = lambda record: warnings.append(record.getMessage())
    logging.getLogger("orkes").addHandler(handler)

    sink = CountingSink(KEY, URL)
    results = []

    def one_run(request):
        recorder = Recorder()
        runner = build([recorder, sink])
        state = {"request": request, "goal": "", "research_plan": "", "area": "", "sources": {},
                 "findings": {}, "messages": [], "pending_tool_calls": [], "draft": "", "review_score": 0,
                 "review_feedback": "", "revision": 0, "report": "", "needs_human": False}
        start = time.time()
        try:
            asyncio.run(runner.arun(state))
        except ConnectionError:
            pass
        wall = time.time() - start
        edges, end = recorder.edges, recorder.end
        run_end = end.start_time + end.elapsed_time
        times = sink.times.get(runner.run_id, [])
        results.append({
            "request": request,
            "expect_failure": parse_request(request)[1] in OUTAGE_CITIES,
            "run_id": runner.run_id,
            "status": end.status,
            "failed_node": end.failed_node,
            "error": (end.error or "").split("\n")[0],
            "seconds": round(end.elapsed_time, 1),
            "end_wait": round(wall - end.elapsed_time, 2),
            "edges": len(edges),
            "contiguous": sorted(e.edge_run_number for e in edges) == list(range(1, len(edges) + 1)),
            "fan_outs": sorted(len(e.to_node) for e in edges if isinstance(e.to_node, list)),
            "loops": sum(n - 1 for n in Counter(e.edge_id for e in edges).values()),
            "function_traces": sum(len(e.function_traces) for e in edges),
            "llm_traces": sum(len(e.llm_traces) for e in edges),
            "escalated": any(e.from_node == "escalate_to_human" for e in edges),
            "requests": sink.sent[runner.run_id],
            "requests_during_run": sum(t < run_end for t in times),
        })

    threads = [threading.Thread(target=one_run, args=(r,)) for r in requests]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    for r in results:
        r["warnings"] = [w[:400] for w in warnings]
        print("RESULT " + json.dumps(r), flush=True)


# --- Launcher: runs the processes and checks every result -------------------------------

# Expected for a run that finishes.
EXPECTED_LOOPS = len(AREAS) * (2 * ANALYST_ROUNDS - 1) + (2 * REVISIONS - 1)
EXPECTED_TOOL_CALLS = len(AREAS) * len(SOURCES) + len(AREAS) * ANALYST_ROUNDS * 2
EXPECTED_LLM_CALLS = 2 + len(AREAS) * (ANALYST_ROUNDS + 1) + 1 + (REVISIONS + 1) + REVISIONS + 1


def check(r):
    problems = []
    if r["expect_failure"]:
        expected = {"status": "FAILED", "failed_node": "regulations_analyst_tools",
                    "error": "ConnectionError: government business registry timed out after 30s"}
    else:
        expected = {"status": "FINISHED", "loops": EXPECTED_LOOPS, "function_traces": EXPECTED_TOOL_CALLS,
                    "llm_traces": EXPECTED_LLM_CALLS, "escalated": True,
                    "fan_outs": [len(SOURCES)] * len(AREAS) + [len(AREAS)]}
        if r["seconds"] < 60:
            problems.append(f"took {r['seconds']}s, expected at least 60s")
    for k, v in expected.items():
        if r[k] != v:
            problems.append(f"{k}: expected {v!r}, got {r[k]!r}")
    if not r["contiguous"]:
        problems.append("edge_run_number is not 1..N")
    if r["requests_during_run"] < 10:
        problems.append(f"only {r['requests_during_run']} requests during the run, so it isn't streaming live")
    for w in r["warnings"]:
        problems.append(f"warning: {w}")
    return problems


def main(one=False):
    """Runs every process, or with one=True a single process with one question."""
    global PROCESS_REQUESTS
    if one:
        PROCESS_REQUESTS = [PROCESS_REQUESTS[0][:1]]
    if not KEY:
        sys.exit("Set ORKES_WATCHER_KEY to a project ingest key (see the watcher's Keys page).")

    server = ThreadingHTTPServer(("127.0.0.1", 0), MockLLM)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    llm_url = f"http://127.0.0.1:{server.server_address[1]}/v1"

    total = sum(len(r) for r in PROCESS_REQUESTS)
    print(f"Sending to {URL}: {len(PROCESS_REQUESTS)} processes, {total} questions, "
          f"{'' if one else 'plus 1 process killed after 30 s'}\n")
    started = time.time()
    procs = [subprocess.Popen([sys.executable, __file__, "--worker", llm_url, json.dumps(requests)],
                              stdout=subprocess.PIPE, text=True) for requests in PROCESS_REQUESTS]
    if not one:
        killed = subprocess.Popen([sys.executable, __file__, "--worker", llm_url, json.dumps([KILLED_REQUEST])],
                                  stdout=subprocess.DEVNULL)
        time.sleep(30)
        killed.kill()

    results = []
    for proc in procs:
        out, _ = proc.communicate(timeout=600)
        results += [json.loads(line[len("RESULT "):]) for line in out.splitlines() if line.startswith("RESULT ")]
    server.shutdown()

    failures = 0
    for r in sorted(results, key=lambda r: (r["expect_failure"], r["request"])):
        problems = check(r)
        failures += bool(problems)
        outcome = f"failed at {r['failed_node']}" if r["status"] == "FAILED" else \
            ("finished, sent to a human" if r["escalated"] else "finished")
        print(f"{'PASS' if not problems else 'FAIL'}  {r['request']}")
        print(f"      {outcome} after {r['seconds']}s | {r['edges']} steps, {r['loops']} repeats, "
              f"{r['llm_traces']} LLM calls, {r['function_traces']} tool calls | "
              f"{r['requests']} batches sent ({r['requests_during_run']} while running), "
              f"waited {r['end_wait']}s at the end | run {r['run_id']}")
        for p in problems:
            print(f"      {p}")
    if len(results) != total:
        failures += 1
        print(f"FAIL  expected {total} results, got {len(results)}")
    if not one:
        print(f"\nKilled mid-run: \"{KILLED_REQUEST}\" should show as running now, then as failed "
              f"(abandoned) after the project's timeout.")
    print(f"Total {time.time() - started:.0f}s, {failures} failing")
    sys.exit(1 if failures else 0)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        worker(sys.argv[2], json.loads(sys.argv[3]))
    else:
        main(one="--one" in sys.argv)
