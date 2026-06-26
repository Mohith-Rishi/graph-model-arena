"""Property tests for Move Validation (Property 15).

**Feature: graph-model-arena, Property 15: Move validation correctness**
**Validates: Requirements 4.2**

Property 15: Move validation correctness
For any move submission, the move SHALL be accepted if and only if the target
node is adjacent to the model's current position AND the connecting edge is
not obstructed.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from graph_model_arena.models import (
    Edge,
    GameConfig,
    GameState,
    Graph,
    GraphConfig,
    ModelState,
    Node,
    NodeType,
)
from graph_model_arena.move_validator import validate_move


# ---------------------------------------------------------------------------
# Custom strategies
# ---------------------------------------------------------------------------


@st.composite
def arbitrary_graph_with_model(draw: st.DrawFn) -> tuple[Graph, str, ModelState]:
    """Generate a random graph with a model placed at a random node.

    Returns (graph, model_id, model_state).
    The graph has a mix of obstructed and unobstructed edges.
    Each pair of nodes has at most one edge (no parallel edges).
    """
    # Generate between 4 and 15 nodes for manageable test cases
    num_nodes = draw(st.integers(min_value=4, max_value=15))
    node_ids = [f"n{i}" for i in range(num_nodes)]

    # Assign start and end
    start_id = node_ids[0]
    end_id = node_ids[-1]

    node_types = [NodeType.START] + [
        draw(st.sampled_from([NodeType.NORMAL, NodeType.TRAP, NodeType.CHECKPOINT, NodeType.POINTS]))
        for _ in range(num_nodes - 2)
    ] + [NodeType.END]

    nodes: dict[str, Node] = {}
    for nid, ntype in zip(node_ids, node_types):
        pv = draw(st.integers(1, 10)) if ntype == NodeType.POINTS else 0
        nodes[nid] = Node(id=nid, node_type=ntype, point_value=pv)

    # Track which pairs already have edges to avoid duplicates
    existing_pairs: set[tuple[str, str]] = set()

    # Build edges: start with a spanning chain to ensure connectivity
    edges: list[Edge] = []
    for i in range(num_nodes - 1):
        cost = draw(st.integers(min_value=1, max_value=10))
        obstructed = draw(st.booleans()) if i > 0 else False  # Keep first edge unobstructed
        src, tgt = node_ids[i], node_ids[i + 1]
        edge_key = (min(src, tgt), max(src, tgt))
        edges.append(Edge(source=src, target=tgt, cost=cost, obstructed=obstructed))
        existing_pairs.add(edge_key)

    # Add some random extra edges (no duplicates)
    num_extra = draw(st.integers(min_value=0, max_value=num_nodes))
    for _ in range(num_extra):
        src_idx = draw(st.integers(min_value=0, max_value=num_nodes - 1))
        tgt_idx = draw(st.integers(min_value=0, max_value=num_nodes - 1))
        if src_idx != tgt_idx:
            src, tgt = node_ids[src_idx], node_ids[tgt_idx]
            edge_key = (min(src, tgt), max(src, tgt))
            if edge_key not in existing_pairs:
                cost = draw(st.integers(min_value=1, max_value=10))
                obstructed = draw(st.booleans())
                edges.append(Edge(source=src, target=tgt, cost=cost, obstructed=obstructed))
                existing_pairs.add(edge_key)

    # Build adjacency
    adjacency: dict[str, list[tuple[str, Edge]]] = {nid: [] for nid in node_ids}
    for edge in edges:
        adjacency[edge.source].append((edge.target, edge))
        adjacency[edge.target].append((edge.source, edge))

    graph = Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node=start_id,
        end_node=end_id,
    )

    # Place model at a random node
    model_node_idx = draw(st.integers(min_value=0, max_value=num_nodes - 1))
    model_node = node_ids[model_node_idx]
    model_id = "test_model"

    model_state = ModelState(
        model_id=model_id,
        strategy_name="test",
        current_node=model_node,
        score=draw(st.integers(min_value=0, max_value=100)),
        visited_nodes={model_node},
        visible_nodes={model_node},
        visible_edges=set(),
    )

    return graph, model_id, model_state


def _make_game_state(graph: Graph, model_state: ModelState) -> GameState:
    """Build a GameState from graph and model."""
    config = GameConfig(graph_config=GraphConfig())
    return GameState(
        graph=graph,
        models={model_state.model_id: model_state},
        current_turn=1,
        max_turns=100,
        config=config,
    )


def _get_adjacent_unobstructed(graph: Graph, current_node: str) -> list[str]:
    """Get all adjacent nodes reachable via unobstructed edges."""
    result = []
    for neighbor_id, edge in graph.adjacency.get(current_node, []):
        if not edge.obstructed:
            result.append(neighbor_id)
    return result


def _get_adjacent_obstructed(graph: Graph, current_node: str) -> list[str]:
    """Get all adjacent nodes where the connecting edge is obstructed."""
    result = []
    for neighbor_id, edge in graph.adjacency.get(current_node, []):
        if edge.obstructed:
            result.append(neighbor_id)
    return result


def _get_non_adjacent(graph: Graph, current_node: str) -> list[str]:
    """Get all nodes that are NOT adjacent to current_node."""
    adjacent = {neighbor_id for neighbor_id, _ in graph.adjacency.get(current_node, [])}
    return [nid for nid in graph.nodes if nid != current_node and nid not in adjacent]


# ---------------------------------------------------------------------------
# Property 15: Move validation correctness — valid moves accepted
# **Validates: Requirements 4.2**
# ---------------------------------------------------------------------------


@settings(max_examples=200, deadline=5000)
@given(graph_data=arbitrary_graph_with_model())
def test_property_15_valid_move_to_adjacent_unobstructed_is_accepted(
    graph_data: tuple[Graph, str, ModelState],
) -> None:
    """For any move to an adjacent node via an unobstructed edge,
    the move SHALL be accepted.

    **Validates: Requirements 4.2**
    """
    graph, model_id, model_state = graph_data
    game_state = _make_game_state(graph, model_state)

    current_node = model_state.current_node
    valid_targets = _get_adjacent_unobstructed(graph, current_node)

    # Test all valid adjacent unobstructed targets
    for target in valid_targets:
        result = validate_move(model_id, target, game_state)
        assert result.valid is True, (
            f"Move from '{current_node}' to adjacent unobstructed node '{target}' "
            f"should be valid but got: {result.reason}"
        )


@settings(max_examples=200, deadline=5000)
@given(graph_data=arbitrary_graph_with_model())
def test_property_15_move_to_non_adjacent_is_rejected(
    graph_data: tuple[Graph, str, ModelState],
) -> None:
    """For any move to a non-adjacent node, the move SHALL be rejected.

    **Validates: Requirements 4.2**
    """
    graph, model_id, model_state = graph_data
    game_state = _make_game_state(graph, model_state)

    current_node = model_state.current_node
    non_adjacent = _get_non_adjacent(graph, current_node)

    # Test all non-adjacent targets
    for target in non_adjacent:
        result = validate_move(model_id, target, game_state)
        assert result.valid is False, (
            f"Move from '{current_node}' to non-adjacent node '{target}' "
            f"should be invalid but was accepted"
        )


@settings(max_examples=200, deadline=5000)
@given(graph_data=arbitrary_graph_with_model())
def test_property_15_move_to_adjacent_obstructed_is_rejected(
    graph_data: tuple[Graph, str, ModelState],
) -> None:
    """For any move to an adjacent node where the connecting edge is obstructed,
    the move SHALL be rejected.

    **Validates: Requirements 4.2**
    """
    graph, model_id, model_state = graph_data
    game_state = _make_game_state(graph, model_state)

    current_node = model_state.current_node
    obstructed_targets = _get_adjacent_obstructed(graph, current_node)

    # Test all obstructed adjacent targets
    for target in obstructed_targets:
        result = validate_move(model_id, target, game_state)
        assert result.valid is False, (
            f"Move from '{current_node}' to adjacent obstructed node '{target}' "
            f"should be invalid but was accepted"
        )


@settings(max_examples=200, deadline=5000)
@given(graph_data=arbitrary_graph_with_model())
def test_property_15_biconditional_completeness(
    graph_data: tuple[Graph, str, ModelState],
) -> None:
    """For any move, acceptance holds if and only if the target is adjacent
    AND the edge is unobstructed. This tests the full biconditional.

    **Validates: Requirements 4.2**
    """
    graph, model_id, model_state = graph_data
    game_state = _make_game_state(graph, model_state)

    current_node = model_state.current_node

    # Build lookup: which targets are adjacent and unobstructed
    adjacent_unobstructed = set(_get_adjacent_unobstructed(graph, current_node))

    # Check every node in the graph
    for target_id in graph.nodes:
        if target_id == current_node:
            continue

        result = validate_move(model_id, target_id, game_state)

        if target_id in adjacent_unobstructed:
            assert result.valid is True, (
                f"Move from '{current_node}' to '{target_id}' should be valid "
                f"(adjacent + unobstructed) but got: {result.reason}"
            )
        else:
            assert result.valid is False, (
                f"Move from '{current_node}' to '{target_id}' should be invalid "
                f"(not adjacent or obstructed) but was accepted"
            )
