import pytest
from orkes.graph.core import OrkesGraph
from typing import TypedDict
import random

# Define the state structure (copied from example for consistency)
class State(TypedDict):
    initial: int
    add_result: int
    multiply_result: int
    condition_result: bool

# Dummy functions for nodes
def add_3(state: State):
    return state

def multiply_by_2(state: State):
    return state

def greater_than_10(state: State):
    return state

def path_true_node(state: State):
    return state

def path_false_node(state: State):
    return state

def conditional_node(state: State):
    # This function's return value will be used by conditional_edge's condition dict.
    # For reachability testing, we need to ensure all branches are explored.
    return random.choice(['true', 'false'])

@pytest.fixture
def complex_graph():
    """
    Fixture to create a complex graph with conditional edges and a loop.
    Graph structure (simplified):
    START -> add_3 -> multiply_by_2 -> greater_than_10
        greater_than_10 (conditional_node) --(true)--> path_true
        greater_than_10 (conditional_node) --(false)--> path_false
    path_false -> multiply_by_2 (loop back)
    path_true -> END
    """
    graph = OrkesGraph(State)
    
    graph.add_node('add_3', add_3)
    graph.add_node('multiply_by_2', multiply_by_2)
    graph.add_node('greater_than_10', greater_than_10)
    graph.add_node('path_true', path_true_node)
    graph.add_node('path_false', path_false_node)

    graph.add_edge(graph.START, 'add_3')
    graph.add_edge('add_3', 'multiply_by_2')
    graph.add_edge('multiply_by_2', 'greater_than_10')
    graph.add_conditional_edge('greater_than_10', conditional_node, {'true' : 'path_true', 'false' : 'path_false'})
    graph.add_edge('path_false', 'multiply_by_2') # Loop back
    graph.add_edge('path_true', graph.END)
    
    # Compile the graph to freeze its structure, though for reachability we only care about definition
    # graph.compile() # Not needed for can_reach_node, which operates on the defined graph.
    return graph

def test_direct_reachability(complex_graph):
    """Test direct reachability between adjacent nodes."""
    assert complex_graph.can_reach_node('add_3', 'multiply_by_2') == True

def test_multi_step_reachability(complex_graph):
    """Test reachability over multiple steps."""
    assert complex_graph.can_reach_node('add_3', 'greater_than_10') == True

def test_reachability_through_true_conditional_branch(complex_graph):
    """Test reachability through a conditional edge's 'true' branch to END."""
    assert complex_graph.can_reach_node('greater_than_10', 'path_true') == True
    assert complex_graph.can_reach_node('greater_than_10', complex_graph.END.name) == True

def test_reachability_through_false_conditional_branch(complex_graph):
    """Test reachability through a conditional edge's 'false' branch."""
    assert complex_graph.can_reach_node('greater_than_10', 'path_false') == True

def test_reachability_through_loop(complex_graph):
    """Test reachability from a node that can loop back to an earlier node."""
    assert complex_graph.can_reach_node('path_false', 'greater_than_10') == True
    assert complex_graph.can_reach_node('path_false', 'path_true') == True # via multiply_by_2 -> greater_than_10 -> path_true
    assert complex_graph.can_reach_node('path_false', complex_graph.END.name) == True

def test_unreachable_node(complex_graph):
    """Test a scenario where the target node is unreachable."""
    # Assuming 'START' cannot be reached from 'add_3'
    assert complex_graph.can_reach_node('add_3', complex_graph.START.name) == False
    # Create an isolated node to ensure it's unreachable
    graph = OrkesGraph(State)
    graph.add_node("isolated_node", add_3)
    assert graph.can_reach_node(graph.START.name, "isolated_node") == False
    assert graph.can_reach_node("isolated_node", graph.START.name) == False

def test_start_to_end_reachability(complex_graph):
    """Test reachability from START to END."""
    assert complex_graph.can_reach_node(complex_graph.START.name, complex_graph.END.name) == True

def test_invalid_node_names(complex_graph):
    """Test that ValueError is raised for non-existent nodes."""
    with pytest.raises(ValueError, match="Start node 'non_existent_start' does not exist."):
        complex_graph.can_reach_node('non_existent_start', 'add_3')
    with pytest.raises(ValueError, match="Target node 'non_existent_target' does not exist."):
        complex_graph.can_reach_node('add_3', 'non_existent_target')
    with pytest.raises(ValueError):
        complex_graph.can_reach_node('non_existent_start', 'non_existent_target')

def test_reachability_from_end_node(complex_graph):
    """Test reachability from the END node."""
    # END node has no outgoing edges, so it cannot reach any other node.
    assert complex_graph.can_reach_node(complex_graph.END.name, 'add_3') == False
    assert complex_graph.can_reach_node(complex_graph.END.name, complex_graph.START.name) == False
    assert complex_graph.can_reach_node(complex_graph.END.name, complex_graph.END.name) == True # Can "reach" itself


def test_detect_loop_through_conditional_edge(complex_graph):
    """detect_loop must not crash on ConditionalEdge/ParallelEdge, whose static
    `to_node` is None (conditional targets are resolved from `condition`,
    parallel targets from `to_nodes`). `complex_graph` loops path_false ->
    multiply_by_2 via a conditional edge, so a loop must be detected."""
    assert complex_graph.detect_loop() == True


def test_detect_loop_false_for_conditional_dag():
    """A conditional edge with no cycle back to an ancestor should report no loop."""
    graph = OrkesGraph(State)
    graph.add_node('add_3', add_3)
    graph.add_node('path_true', path_true_node)
    graph.add_node('path_false', path_false_node)
    graph.add_edge(graph.START, 'add_3')
    graph.add_conditional_edge('add_3', conditional_node, {'true': 'path_true', 'false': 'path_false'})
    graph.add_edge('path_true', graph.END)
    graph.add_edge('path_false', graph.END)
    assert graph.detect_loop() == False


def test_detect_loop_through_parallel_edge():
    """detect_loop must also handle ParallelEdge's multiple `to_nodes`."""
    graph = OrkesGraph(State)
    graph.add_node('add_3', add_3)
    graph.add_node('multiply_by_2', multiply_by_2)
    graph.add_node('greater_than_10', greater_than_10)
    graph.add_edge(graph.START, 'add_3')
    graph.add_parallel_edges('add_3', ['multiply_by_2', 'greater_than_10'], 'multiply_by_2')
    graph.add_edge('greater_than_10', 'multiply_by_2')
    graph.add_edge('multiply_by_2', graph.END)
    assert graph.detect_loop() == False
