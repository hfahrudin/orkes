"""Tests for the trace sink hook and WatcherSink (orkes <-> orkes-watcher trace
contract 1.0, orkes-watcher: working_context/INTEGRATION_AGREEMENT.md).

A small HTTP server in the test stands in for the watcher. When the orkes-watcher
repo sits next to this one (or ORKES_WATCHER_REPO points at it), every request
body is also checked against the watcher's own ingest schema.
"""
import asyncio
import importlib.util
import json
import logging
import os
import subprocess
import sys
import textwrap
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TypedDict

import pytest

from orkes.exporters import TraceSink
from orkes.exporters import watcher as watcher_module
from orkes.exporters.watcher import WatcherSink
from orkes.graph.core import OrkesGraph


# --- Watcher's own schema (optional) ---------------------------------------------

_WATCHER_REPO = Path(os.environ.get("ORKES_WATCHER_REPO", Path(__file__).resolve().parents[3] / "orkes-watcher"))
_SCHEMA_FILE = _WATCHER_REPO / "backend" / "app" / "schemas" / "trace_event.py"


def _load_watcher_schema():
    if not _SCHEMA_FILE.exists():
        return None
    try:
        spec = importlib.util.spec_from_file_location("watcher_trace_event", _SCHEMA_FILE)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    except Exception:
        return None


WATCHER_SCHEMA = _load_watcher_schema()


# --- Fake watcher -------------------------------------------------------------------

class FakeWatcher:
    """Records every request; answers /version and /ingest/events."""

    def __init__(self, supported_majors=(1,), ingest_status=202, ingest_body=None):
        self.supported_majors = list(supported_majors)
        self.ingest_status = ingest_status
        self.ingest_body = ingest_body or {"ok": True}
        self.requests = []
        self.lock = threading.Lock()
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def _reply(self, status, payload):
                data = json.dumps(payload).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                with fake.lock:
                    fake.requests.append({"method": "GET", "path": self.path})
                self._reply(200, {"watcher_version": "0.1.0", "contract": {"supported_majors": fake.supported_majors, "latest": "1.0"}})

            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                with fake.lock:
                    fake.requests.append({"method": "POST", "path": self.path, "headers": dict(self.headers), "body": body})
                self._reply(fake.ingest_status, fake.ingest_body)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_address[1]}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()

    @property
    def posts(self):
        with self.lock:
            return [r for r in self.requests if r["method"] == "POST"]

    @property
    def bodies(self):
        return [json.loads(r["body"]) for r in self.posts]

    def events(self, run_id=None):
        return [e for b in self.bodies if run_id in (None, b["run_id"]) for e in b["events"]]


@pytest.fixture
def fake_watcher():
    watcher_module._compatible.clear()  # the /version check is cached per process
    fake = FakeWatcher()
    yield fake
    fake.close()
    watcher_module._compatible.clear()


def _validate(bodies):
    for body in bodies:
        assert len(json.dumps(body).encode()) <= watcher_module.MAX_BODY_BYTES
        if WATCHER_SCHEMA is not None:
            WATCHER_SCHEMA.IngestBatch.model_validate(body)


# --- Graphs ---------------------------------------------------------------------------

class S(TypedDict):
    n: int
    data: dict


def _step(s: S):
    s["n"] += 1
    return s


def _linear(sink, name="linear", node=_step):
    g = OrkesGraph(S, name=name, description="A small test graph.", trace_sinks=[sink])
    g.add_node("a", node)
    g.add_node("b", _step)
    g.add_edge(g.START, "a")
    g.add_edge("a", "b")
    g.add_edge("b", g.END)
    return g.compile()


def _loop(sink, passes):
    def gate(s: S):
        return "again" if s["n"] < passes else "done"

    g = OrkesGraph(S, name="loop", trace_sinks=[sink])
    g.add_node("loop", _step)
    g.add_edge(g.START, "loop")
    g.add_conditional_edge("loop", gate, {"again": "loop", "done": "END"}, max_passes=passes + 1)
    return g.compile()


# --- Runner fields (O3, O5, O5b) ---------------------------------------------------

def test_edges_have_started_at_and_node_elapsed():
    g = OrkesGraph(S)
    g.add_node("a", _step)
    g.add_edge(g.START, "a")
    g.add_edge("a", g.END)
    runner = g.compile()
    runner.run({"n": 0, "data": {}})

    for edge in runner.trace.edges_trace:
        assert runner.trace.start_time <= edge.started_at <= runner.trace.start_time + runner.trace.elapsed_time
        assert edge.node_elapsed is not None
    assert runner.trace.edges_trace[0].node_elapsed == 0.0  # START runs no function


@pytest.mark.parametrize("use_arun", [False, True])
def test_node_elapsed_excludes_parallel_branches(use_arun):
    """Agreement O5b: a 0.05 s split node fanning out to 0.2 s and 0.3 s branches
    has elapsed ~0.55 but node_elapsed ~0.05 on the parallel edge."""
    def sleeper(seconds):
        def node(s: S):
            time.sleep(seconds)
            return s
        return node

    def join(s: S, branch_results):
        return s

    g = OrkesGraph(S)
    g.add_node("split", sleeper(0.05))
    g.add_node("b1", sleeper(0.2))
    g.add_node("b2", sleeper(0.3))
    g.add_node("join", join)
    g.add_edge(g.START, "split")
    g.add_parallel_edges("split", ["b1", "b2"], "join")
    g.add_edge("b1", "join")
    g.add_edge("b2", "join")
    g.add_edge("join", g.END)
    runner = g.compile()
    if use_arun:
        asyncio.run(runner.arun({"n": 0, "data": {}}))
    else:
        runner.run({"n": 0, "data": {}})

    [parallel] = [e for e in runner.trace.edges_trace if e.edge_type == "__parallel__"]
    assert parallel.elapsed > 0.5
    assert 0.04 < parallel.node_elapsed < 0.15


def test_conditional_node_elapsed_excludes_gate():
    def slow_gate(s: S):
        time.sleep(0.2)
        return "done"

    g = OrkesGraph(S)
    g.add_node("a", _step)
    g.add_edge(g.START, "a")
    g.add_conditional_edge("a", slow_gate, {"done": "END"})
    runner = g.compile()
    runner.run({"n": 0, "data": {}})
    edge = runner.trace.edges_trace[1]
    assert edge.elapsed > 0.2
    assert edge.node_elapsed < 0.1


def _failing_graph(where):
    def boom(s: S):
        raise ValueError("boom")

    g = OrkesGraph(S)
    g.add_node("a", boom if where == "node" else _step)
    g.add_node("b", _step)
    g.add_edge(g.START, "a")
    if where == "gate":
        g.add_conditional_edge("a", boom, {"x": "b"})
    else:
        g.add_edge("a", "b")
    g.add_edge("b", g.END)
    return g.compile()


@pytest.mark.parametrize("where", ["node", "gate"])
def test_failed_node_is_the_edge_in_progress(where):
    """Agreement §2.6: failed_node is the edge's source node, even when the gate failed."""
    runner = _failing_graph(where)
    with pytest.raises(ValueError, match="boom"):
        runner.run({"n": 0, "data": {}})
    assert runner.trace.failed_node == "a"
    assert runner.trace.error.startswith("ValueError: boom\nTraceback (most recent call last):")
    last = runner.trace.edges_trace[-1]
    assert last.from_node == "a"
    if where == "gate":
        assert last.to_node == "N/A"  # no branch was chosen
        assert last.node_elapsed is not None  # the node itself finished
    else:
        assert last.node_elapsed is None  # the node never finished


def test_failed_node_names_the_failing_branch():
    def boom(s: S):
        raise ValueError("branch failed")

    def join(s: S, branch_results):
        return s

    g = OrkesGraph(S)
    g.add_node("split", _step)
    g.add_node("ok", _step)
    g.add_node("bad", boom)
    g.add_node("join", join)
    g.add_edge(g.START, "split")
    g.add_parallel_edges("split", ["ok", "bad"], "join")
    g.add_edge("ok", "join")
    g.add_edge("bad", "join")
    g.add_edge("join", g.END)
    runner = g.compile()
    with pytest.raises(ValueError):
        runner.run({"n": 0, "data": {}})
    assert runner.trace.failed_node == "bad"


def test_error_is_capped_at_8kb_keeping_the_newest_frames():
    # Two functions calling each other, since Python shortens identical repeated frames.
    def ping(n):
        if n == 0:
            raise RuntimeError("deep failure")
        return pong(n - 1)

    def pong(n):
        return ping(n - 1)

    def node(s: S):
        ping(300)

    g = OrkesGraph(S)
    g.add_node("a", node)
    g.add_edge(g.START, "a")
    g.add_edge("a", g.END)
    runner = g.compile()
    with pytest.raises(RuntimeError):
        runner.run({"n": 0, "data": {}})
    error = runner.trace.error
    assert len(error.encode()) <= 8 * 1024
    assert error.startswith("RuntimeError: deep failure\n...\n")
    assert 'raise RuntimeError("deep failure")' in error  # the frame that raised is kept


# --- TraceSink hook (O6) ---------------------------------------------------------------

class RecordingSink(TraceSink):
    def __init__(self):
        self.calls = []
        self.threads = {}

    def on_run_start(self, trace):
        self.calls.append(("start", trace.run_id))

    def on_edge(self, edge_trace):
        self.calls.append(("edge", edge_trace.edge_run_number))

    def on_run_end(self, trace):
        self.calls.append(("end", trace.status))
        self.threads["end"] = threading.get_ident()


def test_sink_receives_start_edges_and_end():
    sink = RecordingSink()
    runner = _linear(sink)
    runner.run({"n": 0, "data": {}})
    assert sink.calls == [("start", runner.run_id), ("edge", 1), ("edge", 2), ("edge", 3), ("end", "FINISHED")]


def test_sink_sees_the_failing_edge_and_failed_status():
    sink = RecordingSink()
    runner = _failing_graph("node")
    runner.trace_sinks = [sink]
    with pytest.raises(ValueError):
        runner.run({"n": 0, "data": {}})
    assert sink.calls[-2:] == [("edge", 2), ("end", "FAILED")]


def test_a_failing_sink_never_breaks_the_run(caplog):
    class BrokenSink(TraceSink):
        def on_run_start(self, trace):
            raise RuntimeError("start")

        def on_edge(self, edge_trace):
            raise RuntimeError("edge")

        def on_run_end(self, trace):
            raise RuntimeError("end")

    runner = _linear(BrokenSink())
    with caplog.at_level(logging.WARNING, logger="orkes"):
        result = runner.run({"n": 0, "data": {}})
    assert result["n"] == 2
    assert runner.trace.status == "FINISHED"
    assert sum("Trace sink" in r.message for r in caplog.records) == 5  # start, 3 edges, end


def test_arun_calls_on_run_end_off_the_event_loop():
    sink = RecordingSink()
    runner = _linear(sink)

    async def main():
        await runner.arun({"n": 0, "data": {}})
        return threading.get_ident()

    loop_thread = asyncio.run(main())
    assert sink.calls[-1] == ("end", "FINISHED")
    assert sink.threads["end"] != loop_thread


def test_trace_sinks_need_tracing():
    with pytest.raises(ValueError, match="trace_sinks need tracing"):
        OrkesGraph(S, traced=False, trace_sinks=[RecordingSink()])


# --- WatcherSink (O7, O8) ---------------------------------------------------------------

def test_run_is_sent_as_first_batch_edges_then_run_end(fake_watcher):
    sink = WatcherSink(api_key="ok_test_key", base_url=fake_watcher.url)
    runner = _linear(sink)
    runner.run({"n": 0, "data": {}})  # returns only after run_end was sent (≤3 s)

    bodies = fake_watcher.bodies
    _validate(bodies)
    assert [r["path"] for r in fake_watcher.requests][0] == "/version"
    first, *rest = bodies
    assert first["events"] == []
    assert first["graph_description"] == "A small test graph."
    assert [n["node_name"] for n in first["nodes"]] == ["START", "END", "a", "b"]
    for body in bodies:
        assert body["contract_version"] == "1.0"
        assert body["sdk"]["name"] == "orkes"
        assert body["run_id"] == runner.run_id
        assert body["graph_name"] == "linear"
    assert fake_watcher.posts[0]["headers"]["Authorization"] == "Bearer ok_test_key"

    events = fake_watcher.events()
    assert [e["kind"] for e in events] == ["edge", "edge", "edge", "run_end"]
    assert [e["edge_run_number"] for e in events[:-1]] == [1, 2, 3]
    assert {"started_at", "node_elapsed", "elapsed", "state_snapshot"} <= set(events[0])
    end = events[-1]
    assert end["status"] == "FINISHED"
    assert end["start_time"] == runner.trace.start_time
    assert end["elapsed_time"] == runner.trace.elapsed_time
    assert end["error"] is None and end["failed_node"] is None


def test_failed_run_is_sent_with_error_and_failed_node(fake_watcher):
    sink = WatcherSink(api_key="k", base_url=fake_watcher.url)
    runner = _failing_graph("gate")
    runner.trace_sinks = [sink]
    with pytest.raises(ValueError):
        runner.run({"n": 0, "data": {}})

    _validate(fake_watcher.bodies)
    *edges, end = fake_watcher.events()
    assert edges[-1]["to_node"] == "N/A"
    assert end["status"] == "FAILED"
    assert end["failed_node"] == "a"
    assert end["error"].startswith("ValueError: boom\n")


def test_long_runs_are_sent_in_batches_in_order(fake_watcher):
    """Edges are sent while the run is still going (every 0.5 s), in order."""
    def slow_gate(s: S):
        time.sleep(0.01)
        return "again" if s["n"] < 150 else "done"

    sink = WatcherSink(api_key="k", base_url=fake_watcher.url)
    g = OrkesGraph(S, name="loop", trace_sinks=[sink])
    g.add_node("loop", _step)
    g.add_edge(g.START, "loop")
    g.add_conditional_edge("loop", slow_gate, {"again": "loop", "done": "END"}, max_passes=200)
    runner = g.compile()
    runner.run({"n": 0, "data": {}})  # ~1.5 s

    bodies = fake_watcher.bodies
    _validate(bodies)
    assert len(bodies) >= 4  # first batch, then edges sent during the run, then the last batch
    events = fake_watcher.events()
    numbers = [e["edge_run_number"] for e in events if e["kind"] == "edge"]
    assert numbers == list(range(1, 152))
    assert events[-1]["kind"] == "run_end"
    assert sum(e["kind"] == "run_end" for e in events) == 1


def test_thirty_runs_on_one_compiled_graph(fake_watcher):
    sink = WatcherSink(api_key="k", base_url=fake_watcher.url)
    runner = _linear(sink)
    run_ids = []
    for _ in range(30):
        runner.run({"n": 0, "data": {}})
        run_ids.append(runner.run_id)

    _validate(fake_watcher.bodies)
    assert len(set(run_ids)) == 30
    for run_id in run_ids:
        events = fake_watcher.events(run_id)
        assert [e["kind"] for e in events] == ["edge", "edge", "edge", "run_end"]


def test_concurrent_runs_are_never_mixed(fake_watcher):
    sink = WatcherSink(api_key="k", base_url=fake_watcher.url)
    run_ids = []

    def work():
        runner = _loop(sink, passes=60)
        runner.run({"n": 0, "data": {}})
        run_ids.append(runner.run_id)

    threads = [threading.Thread(target=work) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    _validate(fake_watcher.bodies)
    for run_id in run_ids:
        events = fake_watcher.events(run_id)
        assert [e["edge_run_number"] for e in events if e["kind"] == "edge"] == list(range(1, 62))
        assert events[-1]["kind"] == "run_end"


def test_large_fields_are_truncated(fake_watcher):
    sink = WatcherSink(api_key="k", base_url=fake_watcher.url)
    runner = _linear(sink)
    runner.run({"n": 0, "data": {"blob": "x" * 300_000}})

    _validate(fake_watcher.bodies)
    snapshot = fake_watcher.events()[0]["state_snapshot"]
    assert snapshot["_truncated"] is True
    assert snapshot["size"] > 300_000
    assert fake_watcher.events()[-1]["status"] == "FINISHED"


def test_requests_stay_under_5mb(fake_watcher):
    """Each snapshot is just under the field limit, so 60 edges must be split."""
    sink = WatcherSink(api_key="k", base_url=fake_watcher.url)
    runner = _loop(sink, passes=59)
    runner.run({"n": 0, "data": {"blob": "x" * 200_000}})

    bodies = fake_watcher.bodies
    _validate(bodies)
    assert max(len(r["body"]) for r in fake_watcher.posts) <= watcher_module.MAX_BODY_BYTES
    assert [e["edge_run_number"] for e in fake_watcher.events() if e["kind"] == "edge"] == list(range(1, 61))


def test_redact_changes_what_is_sent(fake_watcher):
    def redact(event):
        event = dict(event)
        if "state_snapshot" in event:
            event["state_snapshot"] = {"redacted": True}
        if "node_description" in event:
            event["node_description"] = None
        return event

    sink = WatcherSink(api_key="k", base_url=fake_watcher.url, redact=redact)
    runner = _linear(sink)
    runner.run({"n": 0, "data": {"secret": "s3cr3t"}})

    _validate(fake_watcher.bodies)
    raw = b"".join(r["body"] for r in fake_watcher.posts)
    assert b"s3cr3t" not in raw
    assert fake_watcher.events()[0]["state_snapshot"] == {"redacted": True}


def test_unreachable_watcher_delays_the_run_at_most_3s(caplog):
    watcher_module._compatible.clear()
    sink = WatcherSink(api_key="k", base_url="http://127.0.0.1:9")  # nothing listens here
    runner = _linear(sink)
    start = time.time()
    with caplog.at_level(logging.WARNING, logger="orkes.watcher"):
        result = runner.run({"n": 0, "data": {}})
    assert result["n"] == 2
    assert time.time() - start < 3.5
    assert any("Couldn't send run" in r.message for r in caplog.records)
    watcher_module._compatible.clear()


@pytest.mark.parametrize("status, body", [
    (401, {"detail": "bad key"}),
    (403, {"detail": "wrong scope"}),
    (400, {"error": "unsupported_contract_version", "supported": ["2"]}),
])
def test_sink_turns_off_after_rejection(fake_watcher, status, body, caplog):
    fake_watcher.ingest_status, fake_watcher.ingest_body = status, body
    sink = WatcherSink(api_key="k", base_url=fake_watcher.url)
    runner = _linear(sink)
    with caplog.at_level(logging.WARNING, logger="orkes.watcher"):
        runner.run({"n": 0, "data": {}})
        sent = len(fake_watcher.posts)
        runner.run({"n": 0, "data": {}})
    assert sent == 1  # the first batch was rejected; nothing after it
    assert len(fake_watcher.posts) == 1
    assert sum("turned off" in r.message for r in caplog.records) == 1


def test_sink_sends_nothing_to_a_watcher_without_contract_1(fake_watcher, caplog):
    fake_watcher.supported_majors = [2]
    sink = WatcherSink(api_key="k", base_url=fake_watcher.url)
    runner = _linear(sink)
    with caplog.at_level(logging.WARNING, logger="orkes.watcher"):
        runner.run({"n": 0, "data": {}})
    assert fake_watcher.posts == []
    assert sum("doesn't support trace contract 1.0" in r.message for r in caplog.records) == 1


def test_short_script_delivers_run_end_before_exiting(fake_watcher):
    """Agreement §5: a script that exits right after run() must arrive `finished`."""
    script = textwrap.dedent(f"""
        from typing import TypedDict
        from orkes.graph.core import OrkesGraph
        from orkes.exporters.watcher import WatcherSink

        class S(TypedDict):
            n: int

        def a(s: S):
            s["n"] += 1
            return s

        g = OrkesGraph(S, name="script", trace_sinks=[WatcherSink("k", "{fake_watcher.url}")])
        g.add_node("a", a)
        g.add_edge(g.START, "a")
        g.add_edge("a", g.END)
        g.compile().run({{"n": 0}})
    """)
    subprocess.run([sys.executable, "-c", script], check=True, timeout=30)
    events = fake_watcher.events()
    assert events[-1]["kind"] == "run_end"
    assert events[-1]["status"] == "FINISHED"


def test_exit_flushes_edges_of_an_unfinished_run(fake_watcher):
    """A process that exits mid-run still sends the edges it has (no run_end):
    the watcher later marks the run abandoned."""
    script = textwrap.dedent(f"""
        import os, threading, time
        from typing import TypedDict
        from orkes.graph.core import OrkesGraph
        from orkes.exporters.watcher import WatcherSink

        class S(TypedDict):
            n: int

        def a(s: S):
            s["n"] += 1
            return s

        def stuck(s: S):
            time.sleep(60)
            return s

        g = OrkesGraph(S, name="script", trace_sinks=[WatcherSink("k", "{fake_watcher.url}")])
        g.add_node("a", a)
        g.add_node("stuck", stuck)
        g.add_edge(g.START, "a")
        g.add_edge("a", "stuck")
        g.add_edge("stuck", g.END)
        threading.Thread(target=g.compile().run, args=({{"n": 0}},), daemon=True).start()
        time.sleep(0.2)  # edges START->a and a->stuck are done; stuck->END is running
    """)
    subprocess.run([sys.executable, "-c", script], check=True, timeout=30)
    events = fake_watcher.events()
    assert [(e["kind"], e["edge_run_number"]) for e in events] == [("edge", 1), ("edge", 2)]


def test_import_without_requests_explains_the_extra(monkeypatch):
    monkeypatch.setitem(sys.modules, "requests", None)
    spec = importlib.util.spec_from_file_location("watcher_copy", watcher_module.__file__)
    module = importlib.util.module_from_spec(spec)
    with pytest.raises(ImportError, match=r"pip install 'orkes\[watcher\]'"):
        spec.loader.exec_module(module)


def test_watcher_schema_is_available_for_contract_checks():
    """Makes it visible when the cross-repo schema check above is not running."""
    if WATCHER_SCHEMA is None:
        pytest.skip(f"orkes-watcher schema not found at {_SCHEMA_FILE}; payloads only checked by this file's assertions")
    assert uuid.UUID(str(uuid.uuid4()))


def test_sinks_do_not_leave_threads_running(fake_watcher):
    """A sink's sending thread stops once it has nothing left to send, so code
    that creates a sink per run doesn't pile up threads."""
    def sink_threads():
        return [t for t in threading.enumerate() if t.name == "orkes-watcher-sink"]

    for _ in range(20):
        _linear(WatcherSink(api_key="k", base_url=fake_watcher.url)).run({"n": 0, "data": {}})
    deadline = time.time() + watcher_module.IDLE_EXIT + 2
    while sink_threads() and time.time() < deadline:
        time.sleep(0.05)
    assert sink_threads() == []
    assert len(fake_watcher.events()) == 20 * 4  # every run still arrived in full


def test_a_sink_keeps_working_after_its_thread_stopped(fake_watcher):
    sink = WatcherSink(api_key="k", base_url=fake_watcher.url)
    runner = _linear(sink)
    runner.run({"n": 0, "data": {}})
    time.sleep(watcher_module.IDLE_EXIT + 0.5)  # the thread stops
    runner.run({"n": 0, "data": {}})            # and starts again
    assert [e["kind"] for e in fake_watcher.events(runner.run_id)] == ["edge", "edge", "edge", "run_end"]
