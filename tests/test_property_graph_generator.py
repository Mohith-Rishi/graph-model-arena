"""Property tests for Graph Generator (Properties 1-5).

**Feature: graph-model-arena, Properties 1-5: Graph Generator**
**Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**
"""

from __future__ import annotations

from collections import deque

from hypothesis import given, settings
from hypothesis import strategies as st

from graph_model_arena.graph_generator import generate_graph
from graph_model_arena.models import GraphConfig, NodeType


# ---------------------------------------------------------------------------
# Custom strategy: valid GraphConfig
# ---------------------------------------------------------------------------

@st.composite
def arbitrary_graph_config(draw: st.DrawFn) -> GraphConfig:
    return GraphConfig(
        num_nodes=draw(st.integers(min_value=20, max_value=50)),
        edge_density=draw(st.floats(min_value=0.0, max_value=1.0)),
        trap_probability=draw(st.floats(min_value=0.0, max_value=0.3)),
        clue_probability=draw(st.floats(min_value=0.0, max_value=0.2)),
        map_probability=draw(st.floats(min_value=0.0, max_value=0.2)),
        checkpoint_probability=draw(st.floats(min_value=0.0, max_value=0.2)),
        points_probability=draw(st.floats(min_value=0.0, max_value=0.3)),
        obstacle_density=draw(st.floats(min_value=0.0, max_value=0.5)),
        map_reveal_depth=draw(st.integers(min_value=1, max_value=3)),
    )


# ---------------------------------------------------------------------------
# Helper: BFS connectivity check
# ---------------------------------------------------------------------------

def _bfs_all(start: str, adj: dict[str, set[str]]) -> set[str]:
    visited: set[str] = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        for nb in adj[node]:
            if nb not in visited:
                visited.add(nb)
                queue.append(nb)
    return visited


def _build_adj(graph) -> dict[str, set[str]]:
    """Build adjacency from graph edges (all edges, ignoring obstruction)."""
    adj: dict[str, set[str]] = {nid: set() for nid in graph.nodes}
    for edge in graph.edges:
        adj[edge.source].add(edge.target)
        adj[edge.target].add(edge.source)
    return adj


def _build_adj_unobstructed(graph) -> dict[str, set[str]]:
    """Build adjacency from non-obstructed edges only."""
    adj: dict[str, set[str]] = {nid: set() for nid in graph.nodes}
    for edge in graph.edges:
        if not edge.obstructed:
            adj[edge.source].add(edge.target)
            adj[edge.target].add(edge.source)
    return adj


def _path_exists_avoiding(start, end, adj, nodes, avoid_types):
    """BFS path existence avoiding certain node types (except start/end)."""
    visited = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == end:
            return True
        for nb in adj[node]:
            if nb not in visited:
                if nb != end and nodes[nb].node_type in avoid_types:
                    continue
                visited.add(nb)
                queue.append(nb)
    return False


# ---------------------------------------------------------------------------
# Property 1: Generated graphs are connected with correct node count
# **Validates: Requirements 1.1**
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=10000)
@given(config=arbitrary_graph_config())
def test_property_1_connected_with_correct_node_count(config: GraphConfig) -> None:
    """For any valid GraphConfig, the graph is connected and has exactly num_nodes nodes."""
    graph = generate_graph(config)

    # Correct node count
    assert len(graph.nodes) == config.num_nodes

    # Connectivity (using all edges, ignoring obstruction)
    adj = _build_adj(graph)
    first = next(iter(graph.nodes))
    reachable = _bfs_all(first, adj)
    assert len(reachable) == config.num_nodes


# ---------------------------------------------------------------------------
# Property 2: Start and end nodes exist with a valid path
# **Validates: Requirements 1.2, 1.5**
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=10000)
@given(config=arbitrary_graph_config())
def test_property_2_start_end_with_valid_path(config: GraphConfig) -> None:
    """Exactly one START and one END node exist, with a non-obstructed path between them."""
    graph = generate_graph(config)

    start_nodes = [n for n in graph.nodes.values() if n.node_type == NodeType.START]
    end_nodes = [n for n in graph.nodes.values() if n.node_type == NodeType.END]
    assert len(start_nodes) == 1
    assert len(end_nodes) == 1
    assert graph.start_node == start_nodes[0].id
    assert graph.end_node == end_nodes[0].id

    # Path via non-obstructed edges
    adj = _build_adj_unobstructed(graph)
    reachable = _bfs_all(graph.start_node, adj)
    assert graph.end_node in reachable


# ---------------------------------------------------------------------------
# Property 3: A trap-free path exists from start to end
# **Validates: Requirements 1.3**
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=10000)
@given(config=arbitrary_graph_config())
def test_property_3_trap_free_path_exists(config: GraphConfig) -> None:
    """A path from start to end exists that avoids all Trap_Nodes via non-obstructed edges."""
    graph = generate_graph(config)
    adj = _build_adj_unobstructed(graph)
    assert _path_exists_avoiding(
        graph.start_node, graph.end_node, adj, graph.nodes, {NodeType.TRAP}
    )


# ---------------------------------------------------------------------------
# Property 4: All edge costs are in valid range
# **Validates: Requirements 1.6**
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=10000)
@given(config=arbitrary_graph_config())
def test_property_4_edge_costs_in_range(config: GraphConfig) -> None:
    """Every edge has a positive integer cost in [1, 10]."""
    graph = generate_graph(config)
    for edge in graph.edges:
        assert isinstance(edge.cost, int)
        assert 1 <= edge.cost <= 10


# ---------------------------------------------------------------------------
# Property 5: Node types are validly assigned
# **Validates: Requirements 1.4**
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=10000)
@given(config=arbitrary_graph_config())
def test_property_5_node_types_valid(config: GraphConfig) -> None:
    """Every node has a valid type; START/END nodes are not assigned special types."""
    valid_types = set(NodeType)
    special_types = {NodeType.TRAP, NodeType.CLUE, NodeType.MAP, NodeType.CHECKPOINT, NodeType.POINTS}

    graph = generate_graph(config)
    for node in graph.nodes.values():
        assert node.node_type in valid_types

    start = graph.nodes[graph.start_node]
    end = graph.nodes[graph.end_node]
    assert start.node_type == NodeType.START
    assert end.node_type == NodeType.END
    assert start.node_type not in special_types
    assert end.node_type not in special_types
