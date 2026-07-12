from typing import TypedDict
import pytest
from orkes.graph.core import OrkesGraph


class LoopState(TypedDict):
    count: int


def increment(state: LoopState) -> LoopState:
    state['count'] += 1
    return state


def always_loop(state: LoopState) -> str:
    return 'loop'


def build_looping_graph(max_passes: int):
    graph = OrkesGraph(LoopState)
    graph.add_node('increment', increment)
    graph.add_edge(graph.START, 'increment')
    # 'end' is unreachable (always_loop never returns it), but its presence
    # is required so compile() considers END assigned.
    graph.add_conditional_edge('increment', always_loop, {'loop': 'increment', 'end': 'END'}, max_passes=max_passes)
    return graph.compile()


def test_max_passes_allows_exactly_max_passes_executions():
    """max_passes=N must allow exactly N traversals of the edge, then raise on
    the (N+1)th attempt -- not N+1 traversals as before the off-by-one fix."""
    app = build_looping_graph(max_passes=2)
    with pytest.raises(RuntimeError):
        app.run({'count': 0})
    assert app.graph_state['count'] == 2


def test_max_passes_error_message_reports_actual_limit():
    app = build_looping_graph(max_passes=3)
    with pytest.raises(RuntimeError, match="passed 3 times"):
        app.run({'count': 0})
    assert app.graph_state['count'] == 3


@pytest.mark.parametrize("traced", [True, False])
def test_long_running_loop_does_not_hit_recursion_error(traced):
    """A loop with far more iterations than Python's default recursion limit
    (1000) must complete without RecursionError -- traversal is iterative,
    not recursive, so a loop's depth doesn't grow the call stack."""
    graph = OrkesGraph(LoopState, traced=traced)
    graph.add_node('increment', increment)
    graph.add_edge(graph.START, 'increment')

    def gate(state: LoopState) -> str:
        return 'loop' if state['count'] < 5000 else 'end'

    graph.add_conditional_edge('increment', gate, {'loop': 'increment', 'end': 'END'}, max_passes=5000)
    app = graph.compile()
    result = app.run({'count': 0})
    assert result['count'] == 5000
