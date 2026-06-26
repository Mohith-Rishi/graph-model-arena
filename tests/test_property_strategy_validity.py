"""Property tests for Model Strategy Validity (Property 27).

**Feature: graph-model-arena, Property 27: All model strategies produce valid moves**
**Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8**

Property 27: All model strategies produce valid moves
For any of the 8 built-in model strategies and any valid ModelView, the strategy
SHALL return a node ID that is adjacent to the current node in the visible graph.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st

from graph_model_arena.models import ModelView, Node, NodeType
from graph_model_arena.model_interface import ModelStrategy
from graph_model_arena.strategies import (
    RandomWalker,
    GreedyExplorer,
    ShortestPath,
    CautiousNavigator,
    RiskTaker,
    ClueSeeker,
    SprintRunner,
    BalancedStrategist,
)


# ---------------------------------------------------------------------------
# All 8 built-in strategies
# ---------------------------------------------------------------------------

ALL_STRATEGIES: list[type[ModelStrategy]] = [
    RandomWalker,
    GreedyExplorer,
    ShortestPath,
    CautiousNavigator,
    RiskTaker,
    ClueSeeker,
    SprintRunner,
    BalancedStrategist,
]


# ---------------------------------------------------------------------------
# Custom Hypothesis strategies for generating valid ModelViews
# ---------------------------------------------------------------------------


@st.composite
def arbitrary_model_view(draw: st.DrawFn) -> ModelView:
    """Generate a random but valid ModelView.

    Ensures:
    - The graph has at least 3 nodes (current node + at least 1 neighbor + extras)
    - current_node has at least one adjacent non-obstructed edge in visible_edges
    - visible_nodes contains the current_node and all nodes referenced in visible_edges
    - Node types are randomly assigned with valid point values
    """
    # Generate between 3 and 12 nodes for manageable test cases
    num_nodes = draw(st.integers(min_value=3, max_value=12))
    node_ids = [f"n{i}" for i in range(num_nodes)]

    current_node = node_ids[0]

    # Determine how many nodes are neighbors of current_node (at least 1)
    max_neighbors = min(num_nodes - 1, 5)
    num_neighbors = draw(st.integers(min_value=1, max_value=max_neighbors))
    neighbor_ids = node_ids[1 : 1 + num_neighbors]
    other_ids = node_ids[1 + num_neighbors :]

    # Assign node types — ensure at least one node is END for strategies that seek it
    assignable_types = [
        NodeType.NORMAL,
        NodeType.TRAP,
        NodeType.CLUE,
        NodeType.MAP,
        NodeType.CHECKPOINT,
        NodeType.POINTS,
        NodeType.END,
    ]

    visible_nodes: dict[str, Node] = {}

    # Current node gets START or NORMAL type
    current_type = draw(st.sampled_from([NodeType.START, NodeType.NORMAL]))
    visible_nodes[current_node] = Node(
        id=current_node, node_type=current_type, point_value=0
    )

    # Assign types to neighbor nodes
    for nid in neighbor_ids:
        ntype = draw(st.sampled_from(assignable_types))
        pv = draw(st.integers(1, 10)) if ntype == NodeType.POINTS else 0
        visible_nodes[nid] = Node(id=nid, node_type=ntype, point_value=pv)

    # Assign types to other visible nodes
    for nid in other_ids:
        ntype = draw(st.sampled_from(assignable_types))
        pv = draw(st.integers(1, 10)) if ntype == NodeType.POINTS else 0
        visible_nodes[nid] = Node(id=nid, node_type=ntype, point_value=pv)

    # Build visible_edges: edges from current_node to neighbors
    # At least one must be non-obstructed
    visible_edges: list[tuple[str, str, int, bool]] = []

    # First edge is always non-obstructed to guarantee a valid move exists
    first_cost = draw(st.integers(min_value=1, max_value=10))
    visible_edges.append((current_node, neighbor_ids[0], first_cost, False))

    # Remaining edges from current_node to neighbors may be obstructed or not
    for nid in neighbor_ids[1:]:
        cost = draw(st.integers(min_value=1, max_value=10))
        obstructed = draw(st.booleans())
        visible_edges.append((current_node, nid, cost, obstructed))

    # Add some edges between non-current nodes for richer graph
    for i, nid in enumerate(neighbor_ids):
        for other in other_ids:
            if draw(st.booleans()):  # ~50% chance to add edge
                cost = draw(st.integers(min_value=1, max_value=10))
                obstructed = draw(st.booleans())
                visible_edges.append((nid, other, cost, obstructed))
                break  # limit edges per neighbor to keep test fast

    # Add a few edges among other nodes
    for i in range(len(other_ids)):
        for j in range(i + 1, min(i + 2, len(other_ids))):
            if draw(st.booleans()):
                cost = draw(st.integers(min_value=1, max_value=10))
                obstructed = draw(st.booleans())
                visible_edges.append((other_ids[i], other_ids[j], cost, obstructed))

    # Game state metadata
    current_score = draw(st.integers(min_value=0, max_value=100))
    turn_number = draw(st.integers(min_value=1, max_value=100))
    has_checkpoint = draw(st.booleans())
    checkpoint_node = (
        draw(st.sampled_from(node_ids)) if has_checkpoint else None
    )

    return ModelView(
        current_node=current_node,
        visible_nodes=visible_nodes,
        visible_edges=visible_edges,
        current_score=current_score,
        turn_number=turn_number,
        has_checkpoint=has_checkpoint,
        checkpoint_node=checkpoint_node,
    )


def _get_valid_neighbors_from_view(state: ModelView) -> set[str]:
    """Compute valid (non-obstructed) adjacent nodes from a ModelView."""
    current = state.current_node
    neighbors: set[str] = set()
    for source, target, cost, obstructed in state.visible_edges:
        if obstructed:
            continue
        if source == current:
            neighbors.add(target)
        elif target == current:
            neighbors.add(source)
    return neighbors


# ---------------------------------------------------------------------------
# Property 27: All model strategies produce valid moves
# **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8**
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "strategy_cls",
    ALL_STRATEGIES,
    ids=[cls.__name__ for cls in ALL_STRATEGIES],
)
@settings(max_examples=200, deadline=5000)
@given(model_view=arbitrary_model_view())
def test_property_27_strategy_returns_valid_adjacent_node(
    strategy_cls: type[ModelStrategy],
    model_view: ModelView,
) -> None:
    """For any built-in model strategy and any valid ModelView, the strategy
    SHALL return a node ID that is adjacent to the current node via a
    non-obstructed edge in the visible graph.

    **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8**
    """
    strategy = strategy_cls()
    valid_neighbors = _get_valid_neighbors_from_view(model_view)

    # We ensure at least one valid neighbor exists (guaranteed by the generator)
    assume(len(valid_neighbors) > 0)

    result = strategy.decide_move(model_view)

    assert result in valid_neighbors, (
        f"Strategy {strategy.name} returned '{result}' which is not adjacent "
        f"to current_node '{model_view.current_node}' via a non-obstructed edge. "
        f"Valid neighbors: {valid_neighbors}"
    )
