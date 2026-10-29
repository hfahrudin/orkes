"""Trace-structure regression check for sync-only graphs.

The async-support change touched `_traverse_traced`'s call sites indirectly
(new attributes on `Node`/`ConditionalEdge`/`GraphRunner`) without touching
`_traverse_traced` itself. This test pins the exact recorded trace shape
for a small, fixed sync-only graph -- node names/types, edge from/to/type/
meta -- so any future change to trace-building logic that alters this shape
for a plain sync graph is caught immediately, rather than only being caught
incidentally by unrelated tests asserting on final state.

Timestamps/elapsed/state_snapshot content are intentionally excluded from
the comparison (they vary run to run by construction).
"""

from typing import TypedDict

from orkes.graph.core import OrkesGraph


class TraceEquivState(TypedDict):
    value: int
    label: str


def start_step(state: TraceEquivState) -> TraceEquivState:
    state["value"] += 1
    return state


def gate(state: TraceEquivState) -> str:
    return "big" if state["value"] > 0 else "small"


def big_step(state: TraceEquivState) -> TraceEquivState:
    state["label"] = "big"
    return state


def _build_app():
    graph = OrkesGraph(state=TraceEquivState, name="trace_equiv_graph")
    graph.add_node("start_step", start_step)
    graph.add_node("big_step", big_step)
    graph.add_edge(graph.START, "start_step")
    graph.add_conditional_edge("start_step", gate, {"big": "big_step", "small": "END"})
    graph.add_edge("big_step", graph.END)
    return graph.compile()


def _structural_view(traces_schema):
    """Strips timing/state-content fields, keeping only the shape that
    should be identical across runs of the same sync-only graph."""
    return {
        "nodes": sorted(
            (nt.node_name, nt.meta.get("type")) for nt in traces_schema.nodes_trace
        ),
        "edges": [
            {
                "from_node": et.from_node,
                "to_node": et.to_node,
                "edge_type": et.edge_type,
            }
            for et in traces_schema.edges_trace
        ],
    }


EXPECTED_STRUCTURE = {
    "nodes": sorted(
        [
            ("START", "start_node"),
            ("END", "end_node"),
            ("start_step", "function_node"),
            ("big_step", "function_node"),
        ]
    ),
    "edges": [
        {"from_node": "START", "to_node": "start_step", "edge_type": "__forward__"},
        {"from_node": "start_step", "to_node": "big_step", "edge_type": "__conditional__"},
        {"from_node": "big_step", "to_node": "END", "edge_type": "__forward__"},
    ],
}


def test_traced_run_matches_pinned_structure():
    app = _build_app()
    app.run({"value": 0, "label": ""})

    assert _structural_view(app.trace) == EXPECTED_STRUCTURE


def test_two_runs_of_the_same_graph_produce_structurally_identical_traces():
    """Determinism check: re-running the same compiled graph (with edge
    pass counters reset) must yield the same trace shape both times --
    proving the shape is a property of the graph, not incidental to one run.
    """
    app = _build_app()
    app.run({"value": 0, "label": ""})
    first = _structural_view(app.trace)

    # Reset per-edge pass counters and re-run against a fresh compiled
    # instance to avoid any run-to-run instance-state carryover.
    app2 = _build_app()
    app2.run({"value": 0, "label": ""})
    second = _structural_view(app2.trace)

    assert first == second == EXPECTED_STRUCTURE
