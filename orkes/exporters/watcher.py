"""Sends orkes traces to Orkes Watcher, following trace contract 1.0
(orkes-watcher: working_context/INTEGRATION_AGREEMENT.md).

    from orkes.exporters.watcher import WatcherSink

    sink = WatcherSink(api_key="<project ingest key>", base_url="http://localhost:8000")
    graph = OrkesGraph(MyState, name="my-graph", trace_sinks=[sink])

State snapshots, prompts and LLM replies are sent as they are, unless `redact`
changes them. Delivery is best effort: a failed send is logged and dropped,
never retried, and never affects the run.
"""
import atexit
import json
import logging
import threading
import time
import weakref
from typing import Callable, Dict, List, Optional

import requests

from orkes.exporters import TraceSink
from orkes.graph.schema import EdgeTrace, TracesSchema
from orkes.shared.context import trace_var
from orkes.shared.schema import to_dict

logger = logging.getLogger("orkes.watcher")

CONTRACT_VERSION = "1.0"

MAX_FIELD_BYTES = 256 * 1024  # a larger field is replaced by a "_truncated" marker
MAX_BODY_BYTES = 5 * 1024 * 1024
MAX_BATCH_EVENTS = 5000
MAX_QUEUED_EVENTS = 10_000  # across all runs; newer events are dropped when full
FLUSH_EVENTS = 50  # send a run's events once this many are queued...
FLUSH_INTERVAL = 0.5  # ...or this many seconds have passed
END_WAIT = 3.0  # longest on_run_end (and the exit handler) waits for sending
REQUEST_TIMEOUT = 5.0
IDLE_EXIT = 1.0  # the sending thread stops after this long with nothing to send

# Result of GET /version per watcher address, checked once per process.
_compatible: Dict[str, bool] = {}
_compatible_lock = threading.Lock()

# Every sink still in use, so one exit handler can flush them all.
_sinks: "weakref.WeakSet[WatcherSink]" = weakref.WeakSet()


@atexit.register
def _flush_all_at_exit() -> None:
    """Gives every sink's queue one last send, END_WAIT seconds in total."""
    deadline = time.monotonic() + END_WAIT
    for sink in list(_sinks):
        sink._flush_at_exit(max(0.0, deadline - time.monotonic()))


_SDK: Optional[Dict[str, str]] = None


def _sdk_info() -> Dict[str, str]:
    global _SDK
    if _SDK is None:
        import orkes

        _SDK = {"name": "orkes", "version": orkes.__version__}
    return _SDK


def _field_json(value) -> str:
    """One field as JSON, or a "_truncated" marker if it's over MAX_FIELD_BYTES."""
    text = json.dumps(value, default=str)
    size = len(text.encode())
    if size > MAX_FIELD_BYTES:
        return json.dumps({"_truncated": True, "size": size})
    return text


def _object_json(obj: dict) -> str:
    """A dict as JSON, with each top-level field size-limited."""
    return "{" + ",".join(f"{json.dumps(str(k))}:{_field_json(v)}" for k, v in obj.items()) + "}"


class _Run:
    """What's queued for one run, and whether its last batch has been sent."""

    def __init__(self, run_id: str, graph_name: str):
        self.run_id = run_id
        self.graph_name = graph_name
        self.first: Optional[dict] = None  # graph_description + nodes, sent once
        self.edges: List[EdgeTrace] = []
        self.end: Optional[dict] = None
        self.end_taken = False
        self.done = threading.Event()  # set once the run_end batch was sent or dropped
        self.warned_full = False
        self.warned_send = False


class WatcherSink(TraceSink):
    """A trace sink that sends each run to Orkes Watcher.

    Args:
        api_key (str): A project ingest key from the watcher.
        base_url (str): The watcher backend's address (default deploy:
            `http://<host>:8000`), not the dashboard's.
        redact (Callable[[dict], dict], optional): Called on every event and
            every node entry before it's sent; what it returns is sent instead.
            Use it to remove secrets or personal data from state and prompts.

    Create one sink and reuse it for all your graphs and runs. The run's thread
    only adds to an in-memory queue; one background thread per sink does all
    sending, and stops by itself when there is nothing left to send. `on_run_end` waits up to 3 seconds for the
    run's data to be sent, so short scripts don't exit before it arrives.
    After a 401/403 or an unsupported contract version, the sink logs one
    warning and stops sending for the rest of the process.
    """

    def __init__(self, api_key: str, base_url: str, redact: Optional[Callable[[dict], dict]] = None):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.redact = redact
        self._runs: Dict[str, _Run] = {}
        self._queued = 0
        self._cond = threading.Condition()
        self._worker: Optional[threading.Thread] = None
        self._disabled = False
        self._closing = False
        self._sending = False  # the worker holds taken data it hasn't sent yet
        _sinks.add(self)

    # --- TraceSink -------------------------------------------------------------

    def on_run_start(self, trace: TracesSchema) -> None:
        if self._disabled:
            return
        with self._cond:
            run = self._get_run(trace.run_id, trace.graph_name)
            run.first = {"graph_description": trace.graph_description, "nodes": list(trace.nodes_trace)}
            self._cond.notify()
        self._ensure_worker()

    def on_edge(self, edge_trace: EdgeTrace) -> None:
        trace = trace_var.get()
        if self._disabled or trace is None:
            return
        with self._cond:
            run = self._get_run(trace.run_id, trace.graph_name)
            if self._queued >= MAX_QUEUED_EVENTS:
                if not run.warned_full:
                    run.warned_full = True
                    logger.warning("Watcher queue is full (%d events); dropping events of run %s", MAX_QUEUED_EVENTS, run.run_id)
                return
            run.edges.append(edge_trace)
            self._queued += 1
            if len(run.edges) >= FLUSH_EVENTS:
                self._cond.notify()
        self._ensure_worker()

    def on_run_end(self, trace: TracesSchema) -> None:
        if self._disabled:
            return
        with self._cond:
            run = self._get_run(trace.run_id, trace.graph_name)
            run.end = {
                "kind": "run_end",
                "status": trace.status,
                "start_time": trace.start_time,
                "elapsed_time": trace.elapsed_time,
                "error": trace.error,
                "failed_node": trace.failed_node,
            }
            self._cond.notify()
        self._ensure_worker()
        run.done.wait(END_WAIT)

    # --- queue ----------------------------------------------------------------

    def _get_run(self, run_id: str, graph_name: str) -> _Run:
        run = self._runs.get(run_id)
        if run is None:
            run = self._runs[run_id] = _Run(run_id, graph_name)
        return run

    def _ensure_worker(self) -> None:
        with self._cond:
            if self._worker is not None or self._disabled:
                return
            self._worker = threading.Thread(target=self._work, name="orkes-watcher-sink", daemon=True)
            self._worker.start()

    def _flush_at_exit(self, timeout: float = END_WAIT) -> None:
        """Gives anything still queued one last send, waiting at most `timeout`
        seconds. A run that never ended gets no run_end; the watcher marks it
        abandoned."""
        with self._cond:
            if self._worker is None:
                return
            self._closing = True
            self._cond.notify_all()
            self._cond.wait_for(
                lambda: self._disabled or not (
                    self._sending
                    or any(r.first is not None or r.edges or (r.end and not r.end_taken) for r in self._runs.values())
                ),
                timeout=timeout,
            )

    def _urgent(self) -> bool:
        """Whether something should be sent now rather than at the next tick."""
        for r in self._runs.values():
            if r.first is not None or len(r.edges) >= FLUSH_EVENTS or (r.end is not None and not r.end_taken):
                return True
            if self._closing and r.edges:
                return True
        return False

    def _take(self):
        """Removes everything queued, per run: (run, first, edges, end)."""
        taken = []
        for run in list(self._runs.values()):
            end = None
            if run.end is not None and not run.end_taken:
                end, run.end_taken = run.end, True
            if run.first is None and not run.edges and end is None:
                continue
            taken.append((run, run.first, run.edges, end))
            self._queued -= len(run.edges)
            run.first, run.edges = None, []
        return taken

    def _work(self) -> None:
        session = requests.Session()
        try:
            self._send_loop(session)
        finally:
            session.close()

    def _send_loop(self, session) -> None:
        while True:
            with self._cond:
                if not self._runs:
                    # Nothing in progress: stop after a short grace period, so a
                    # sink that's no longer used doesn't keep a thread alive.
                    self._cond.wait_for(lambda: self._runs or self._disabled, timeout=IDLE_EXIT)
                if self._disabled or not self._runs:
                    self._worker = None
                    self._cond.notify_all()
                    return
                self._cond.wait_for(self._urgent, timeout=FLUSH_INTERVAL)
                if self._disabled:
                    self._worker = None
                    return
                taken = self._take()
                self._sending = bool(taken)
            if taken and self._check_version(session):
                for run, first, edges, end in taken:
                    try:
                        self._send_run(session, run, first, edges, end)
                    except Exception:
                        # Never let one bad run stop the worker for every other run.
                        logger.warning("Couldn't prepare data of run %s for Orkes Watcher", run.run_id, exc_info=True)
            for run, _, _, end in taken:
                if end is not None:
                    self._finish(run)
            with self._cond:
                self._sending = False
                if self._closing:
                    self._cond.notify_all()

    def _finish(self, run: _Run) -> None:
        with self._cond:
            self._runs.pop(run.run_id, None)
            self._cond.notify_all()
        run.done.set()

    def _disable(self, reason: str) -> None:
        logger.warning("Orkes Watcher sink turned off for this process: %s", reason)
        with self._cond:
            self._disabled = True
            runs = list(self._runs.values())
            self._runs.clear()
            self._queued = 0
            self._cond.notify_all()
        for run in runs:
            run.done.set()

    # --- sending ----------------------------------------------------------------

    def _check_version(self, session) -> bool:
        """Checks once per process that the watcher supports this contract's
        major version. An unreachable watcher is not treated as incompatible:
        sends will fail and be logged on their own."""
        with _compatible_lock:
            if self.base_url not in _compatible:
                compatible = True
                try:
                    response = session.get(f"{self.base_url}/version", timeout=REQUEST_TIMEOUT)
                    if response.ok:
                        majors = response.json()["contract"]["supported_majors"]
                        compatible = int(CONTRACT_VERSION.split(".")[0]) in [int(m) for m in majors]
                except (requests.RequestException, ValueError, KeyError, TypeError):
                    pass
                _compatible[self.base_url] = compatible
            compatible = _compatible[self.base_url]
        if not compatible:
            self._disable(f"the watcher at {self.base_url} doesn't support trace contract {CONTRACT_VERSION}")
        return compatible

    def _redacted(self, obj: dict) -> Optional[dict]:
        if self.redact is None:
            return obj
        try:
            return self.redact(obj)
        except Exception:
            logger.warning("Watcher redact function failed; event not sent", exc_info=True)
            return None

    def _send_run(self, session, run: _Run, first, edges, end) -> None:
        envelope = {"contract_version": CONTRACT_VERSION, "sdk": _sdk_info(), "run_id": run.run_id, "graph_name": run.graph_name}

        if first is not None:
            nodes = [self._redacted(to_dict(n)) for n in first["nodes"]]
            body = dict(envelope, graph_description=first["graph_description"], events=[])
            head = json.dumps({k: v for k, v in body.items() if k != "nodes"}, default=str)
            nodes_json = "[" + ",".join(_object_json(n) for n in nodes if n is not None) + "]"
            self._post(session, run, head[:-1] + ', "nodes": ' + nodes_json + "}")

        events = []
        for edge in edges:
            event = self._redacted({"kind": "edge", **to_dict(edge)})
            if event is not None:
                events.append(_object_json(event))
        if end is not None:
            events.append(_object_json(end))  # never redacted away: it closes the run
        if not events:
            return

        head = json.dumps(envelope)[:-1] + ', "events": ['
        head_bytes = len(head.encode()) + 2
        batch, size = [], head_bytes
        for event in events:
            event_bytes = len(event.encode()) + 1
            if batch and (len(batch) >= MAX_BATCH_EVENTS or size + event_bytes > MAX_BODY_BYTES):
                self._post(session, run, head + ",".join(batch) + "]}")
                batch, size = [], head_bytes
            batch.append(event)
            size += event_bytes
        self._post(session, run, head + ",".join(batch) + "]}")

    def _post(self, session, run: _Run, body: str) -> None:
        if self._disabled:
            return
        try:
            response = session.post(
                f"{self.base_url}/ingest/events",
                data=body.encode(),
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                timeout=REQUEST_TIMEOUT,
            )
        except requests.RequestException as e:
            if not run.warned_send:
                run.warned_send = True
                logger.warning("Couldn't send run %s to Orkes Watcher at %s: %s", run.run_id, self.base_url, e)
            return

        code = response.status_code
        if 200 <= code < 300:
            return
        if code in (401, 403):
            self._disable(f"the watcher rejected the API key ({code})")
        elif code == 400 and _error_code(response) == "unsupported_contract_version":
            self._disable(f"the watcher doesn't support trace contract {CONTRACT_VERSION}")
        elif code >= 500:
            if not run.warned_send:
                run.warned_send = True
                logger.warning("Orkes Watcher is unavailable (%d); data of run %s dropped", code, run.run_id)
        else:
            logger.warning("Orkes Watcher rejected data of run %s (%d): %s", run.run_id, code, response.text[:2000])


def _error_code(response) -> Optional[str]:
    try:
        return response.json().get("error")
    except (ValueError, AttributeError):
        return None


__all__ = ["WatcherSink", "CONTRACT_VERSION"]
