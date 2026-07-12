from typing import TypedDict
import pytest
from orkes.graph.core import OrkesGraph


class GateState(TypedDict):
    x: int


def noop(state: GateState) -> GateState:
    return state


def bad_gate(state: GateState) -> str:
    # Simulates a typo/bug: returns a value not present in the condition map.
    return 'yes'


@pytest.mark.parametrize("traced", [True, False])
def test_gate_function_invalid_return_raises_informative_keyerror(traced):
    """A gate function returning a value absent from its condition map used to
    surface as a bare `KeyError: 'yes'` with no indication of which node or
    what the valid options were. It must now name the node, the bad value,
    and the valid keys."""
    graph = OrkesGraph(GateState, traced=traced)
    graph.add_node('n1', noop)
    graph.add_edge(graph.START, 'n1')
    graph.add_conditional_edge('n1', bad_gate, {'true': 'END', 'false': 'END'})
    app = graph.compile()

    with pytest.raises(KeyError, match="Gate function on node 'n1' returned 'yes'.*\\['true', 'false'\\]"):
        app.run({'x': 0})
