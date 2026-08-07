"""Regression checks for the async-support change: the new attributes
(`Node.is_async`, `ConditionalEdge.is_async_gate`,
`GraphRunner.has_async_components`, `GraphRunner._running`) must be purely
additive -- present with correct `False` defaults on every existing
sync-only graph, and must never change `__init__`'s prior behavior or raise
on old-style graph construction.

Exercises `tests/examples/complex_graph_test.py`'s module-level `runner`,
which -- unlike the other example scripts -- builds a graph at import time
covering every construct: plain `Node`, `ConditionalEdge` (loop gates),
`ParallelEdge`, and `AggregationNode` (via `add_parallel_edges`), with no
live external dependencies (unlike `graph_service_test.py`, which needs an
LLM API key and only builds its graph inside `if __name__ == "__main__":`).
"""

import importlib
import sys
from pathlib import Path

import pytest

from orkes.graph.unit import AggregationNode, ConditionalEdge, ForwardEdge, ParallelEdge

EXAMPLES_DIR = Path(__file__).resolve().parents[1] / "examples"


@pytest.fixture(scope="module")
def complex_graph_runner():
    sys.path.insert(0, str(EXAMPLES_DIR))
    try:
        module = importlib.import_module("complex_graph_test")
    finally:
        sys.path.remove(str(EXAMPLES_DIR))
    return module.runner


def test_graph_runner_level_attributes_default_correctly(complex_graph_runner):
    assert complex_graph_runner.has_async_components is False
    assert complex_graph_runner._running is False


def test_every_node_is_async_defaults_false(complex_graph_runner):
    node_pool_items = complex_graph_runner.nodes_pool.values()
    assert len(node_pool_items) > 0  # sanity: the fixture actually has nodes

    for node_pool_item in node_pool_items:
        assert node_pool_item.node.is_async is False, (
            f"Node '{node_pool_item.node.name}' should default is_async=False "
            "for a purely sync graph"
        )


def test_aggregation_nodes_covered_and_default_false(complex_graph_runner):
    aggregation_nodes = [
        item.node
        for item in complex_graph_runner.nodes_pool.values()
        if isinstance(item.node, AggregationNode)
    ]
    # complex_graph_test.py wires 3 aggregation points (branch_a, branch_b, main)
    assert len(aggregation_nodes) == 3

    for node in aggregation_nodes:
        assert node.is_async is False


def test_every_conditional_edge_is_async_gate_defaults_false(complex_graph_runner):
    conditional_edges = [
        item.edge
        for item in complex_graph_runner.nodes_pool.values()
        if isinstance(item.edge, ConditionalEdge)
    ]
    # complex_graph_test.py wires 2 loop gates (loop_a, loop_b)
    assert len(conditional_edges) == 2

    for edge in conditional_edges:
        assert edge.is_async_gate is False


def test_forward_and_parallel_edges_present_and_unaffected(complex_graph_runner):
    """Sanity check that the fixture graph actually exercises ForwardEdge and
    ParallelEdge too, so this file's coverage claim (every construct type) is
    verified, not assumed."""
    edges = [item.edge for item in complex_graph_runner.nodes_pool.values() if item.edge]

    assert any(isinstance(e, ForwardEdge) for e in edges)
    assert any(isinstance(e, ParallelEdge) for e in edges)


def test_complex_graph_can_still_run_via_run_after_the_change(complex_graph_runner):
    """The example graph already ran once at import time (module-level
    side effect); confirm it can also be run again via the ordinary sync
    `run()` entry point without the new guards misfiring on a purely-sync
    graph.

    Note: `main_aggregator` (like `branch_a_aggregator`/`branch_b_aggregator`)
    deliberately ignores `branch_results` and returns the pre-fork snapshot
    unchanged -- so the final state's loop-exit flags revert to their
    pre-fork values, not each branch's internal final value. This mirrors
    `test_complex_parallel_graph.py`'s `two_param_agg_ignoring_results`
    pattern; this test only checks that `run()` completes and returns the
    expected shape, not business-logic values the aggregators intentionally
    discard.
    """
    # Re-running mutates instance state (run_number, trace, passes on each
    # edge) -- reset the per-edge pass counters the same way the statebloat
    # benchmark does between iterations, so max_passes isn't hit early.
    for node_pool_item in complex_graph_runner.nodes_pool.values():
        if node_pool_item.edge is not None and hasattr(node_pool_item.edge, "passes"):
            node_pool_item.edge.passes = 0

    fresh_state = {
        "main_counter": 0,
        "branch_a_counter": 0,
        "branch_b_counter": 0,
        "branch_a_sub_branch_counters": [],
        "branch_b_sub_branch_counters": [],
        "branch_a_loop_exit": False,
        "branch_b_loop_exit": False,
    }
    result = complex_graph_runner.run(fresh_state)
    assert set(fresh_state.keys()) <= set(result.keys())
    assert isinstance(result["branch_a_loop_exit"], bool)
    assert isinstance(result["branch_b_loop_exit"], bool)
