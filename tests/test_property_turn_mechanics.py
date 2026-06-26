"""Property tests for Turn Mechanics (Properties 16-19).

**Feature: graph-model-arena, Properties 16-19: Turn Mechanics**
**Validates: Requirements 4.3, 4.4, 4.5, 4.6, 5.3**

Property 16: Invalid move penalty
Property 17: Simultaneous move resolution is order-independent
Property 18: Completion bonus calculation
Property 19: Timeout results in no-op without penalty
"""

from __future__ import annotations

import copy
import itertools
import time

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from graph_model_arena.model_interface import ModelStrategy
from graph_model_arena.models import (
    Edge,
    GameConfig,
    GameState,
    Graph,
    GraphConfig,
    ModelState,
    ModelView,
    Node,
    NodeType,
    ValidatedMove,
)
from graph_model_arena.move_validator import validate_move
from graph_model_arena.score_manager import apply_completion_bonus, apply_invalid_move_penalty
from graph_model_arena.state_resolver import resolve_moves
from graph_model_arena.turn_manager import execute_turn


# ---------------------------------------------------------------------------
# Helper strategies / test models
# ---------------------------------------------------------------------------


class FixedMoveStrategy(ModelStrategy):
    """A strategy that always returns a fixed target node."""

    def __init__(self, target: str):
        self._target = target

    def decide_move(self, state: ModelView) -> str:
        return self._target


class TimeoutStrategy(ModelStrategy):
    """A strategy that sleeps longer than any reasonable timeout."""

    def __init__(self, delay: float = 10.0):
        self._delay = delay

    def decide_move(self, state: ModelView) -> str:
        time.sleep(self._delay)
        return "unreachable"


# ---------------------------------------------------------------------------
# Custom Hypothesis strategies
# ---------------------------------------------------------------------------


@st.composite
def arbitrary_graph_with_model_and_invalid_target(
    draw: st.DrawFn,
) -> tuple[Graph, str, ModelState, str]:
    """Generate a graph with a model placed at a node, plus an invalid target.

    Returns (graph, model_id, model_state, invalid_target_node).
    The invalid target is guaranteed to be either non-adjacent or via obstructed edge.
    """
    num_nodes = draw(st.integers(min_value=4, max_value=12))
    node_ids = [f"n{i}" for i in range(num_nodes)]

    start_id = node_ids[0]
    end_id = node_ids[-1]

    nodes: dict[str, Node] = {
        start_id: Node(id=start_id, node_type=NodeType.START),
        end_id: Node(id=end_id, node_type=NodeType.END),
    }
    for nid in node_ids[1:-1]:
        nodes[nid] = Node(id=nid, node_type=NodeType.NORMAL)

    # Build edges (spanning chain, all unobstructed to start)
    edges: list[Edge] = []
    existing_pairs: set[tuple[str, str]] = set()
    for i in range(num_nodes - 1):
        cost = draw(st.integers(min_value=1, max_value=10))
        src, tgt = node_ids[i], node_ids[i + 1]
        edge_key = (min(src, tgt), max(src, tgt))
        edges.append(Edge(source=src, target=tgt, cost=cost, obstructed=False))
        existing_pairs.add(edge_key)

    # Add a few random extra edges
    num_extra = draw(st.integers(min_value=0, max_value=num_nodes // 2))
    for _ in range(num_extra):
        src_idx = draw(st.integers(min_value=0, max_value=num_nodes - 1))
        tgt_idx = draw(st.integers(min_value=0, max_value=num_nodes - 1))
        if src_idx != tgt_idx:
            src, tgt = node_ids[src_idx], node_ids[tgt_idx]
            edge_key = (min(src, tgt), max(src, tgt))
            if edge_key not in existing_pairs:
                cost = draw(st.integers(min_value=1, max_value=10))
                edges.append(Edge(source=src, target=tgt, cost=cost, obstructed=False))
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

    # Place model at a node that has non-adjacent nodes
    model_node_idx = draw(st.integers(min_value=0, max_value=num_nodes - 1))
    model_node = node_ids[model_node_idx]
    model_id = "test_model"

    # Find non-adjacent nodes for invalid target
    adjacent_ids = {nid for nid, _ in adjacency[model_node]}
    non_adjacent = [nid for nid in node_ids if nid != model_node and nid not in adjacent_ids]

    # We need at least one non-adjacent node
    assume(len(non_adjacent) > 0)

    invalid_target = draw(st.sampled_from(non_adjacent))

    initial_score = draw(st.integers(min_value=0, max_value=500))
    model_state = ModelState(
        model_id=model_id,
        strategy_name="test",
        current_node=model_node,
        score=initial_score,
        visited_nodes={model_node},
        visible_nodes=set(node_ids),
        visible_edges={(min(e.source, e.target), max(e.source, e.target)) for e in edges},
    )

    return graph, model_id, model_state, invalid_target


@st.composite
def arbitrary_graph_with_multiple_valid_moves(
    draw: st.DrawFn,
) -> tuple[Graph, list[ValidatedMove], dict[str, ModelState]]:
    """Generate a graph with multiple models, each having a valid move.

    Returns (graph, list_of_valid_moves, model_states_dict).
    All moves are guaranteed valid (adjacent, unobstructed).
    """
    # Build a star-like graph: center connected to many leaves
    num_leaves = draw(st.integers(min_value=3, max_value=8))
    center_id = "center"
    leaf_ids = [f"leaf_{i}" for i in range(num_leaves)]
    end_id = "end"

    nodes: dict[str, Node] = {
        center_id: Node(id=center_id, node_type=NodeType.START),
        end_id: Node(id=end_id, node_type=NodeType.END),
    }
    for lid in leaf_ids:
        nodes[lid] = Node(id=lid, node_type=NodeType.NORMAL)

    edges: list[Edge] = []
    for lid in leaf_ids:
        cost = draw(st.integers(min_value=1, max_value=10))
        edges.append(Edge(source=center_id, target=lid, cost=cost, obstructed=False))
    # Connect end to one leaf
    edges.append(Edge(source=leaf_ids[0], target=end_id, cost=1, obstructed=False))

    adjacency: dict[str, list[tuple[str, Edge]]] = {nid: [] for nid in nodes}
    for edge in edges:
        adjacency[edge.source].append((edge.target, edge))
        adjacency[edge.target].append((edge.source, edge))

    graph = Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node=center_id,
        end_node=end_id,
    )

    # Place 2-4 models at center, each moving to a different leaf
    num_models = draw(st.integers(min_value=2, max_value=min(4, num_leaves)))
    target_indices = draw(
        st.lists(
            st.integers(min_value=0, max_value=num_leaves - 1),
            min_size=num_models,
            max_size=num_models,
            unique=True,
        )
    )

    model_states: dict[str, ModelState] = {}
    moves: list[ValidatedMove] = []

    for i in range(num_models):
        model_id = f"model_{i}"
        target = leaf_ids[target_indices[i]]
        score = draw(st.integers(min_value=0, max_value=200))

        model_states[model_id] = ModelState(
            model_id=model_id,
            strategy_name="test",
            current_node=center_id,
            score=score,
            visited_nodes={center_id},
            visible_nodes=set(nodes.keys()),
            visible_edges={(min(e.source, e.target), max(e.source, e.target)) for e in edges},
        )
        moves.append(ValidatedMove(model_id=model_id, target_node=target, valid=True))

    return graph, moves, model_states


@st.composite
def arbitrary_completion_scenario(
    draw: st.DrawFn,
) -> tuple[ModelState, int, int, float]:
    """Generate a random completion bonus scenario.

    Returns (model_state, turns_taken, max_turns, multiplier).
    Ensures turns_taken <= max_turns.
    """
    max_turns = draw(st.integers(min_value=10, max_value=500))
    turns_taken = draw(st.integers(min_value=1, max_value=max_turns))
    multiplier = draw(st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False))
    initial_score = draw(st.integers(min_value=0, max_value=1000))

    model_state = ModelState(
        model_id="model_finish",
        strategy_name="test",
        current_node="end",
        score=initial_score,
        has_finished=True,
        turns_taken=turns_taken,
        visited_nodes={"start", "end"},
        visible_nodes={"start", "end"},
        visible_edges=set(),
    )

    return model_state, turns_taken, max_turns, multiplier


# ---------------------------------------------------------------------------
# Helper to build GameState
# ---------------------------------------------------------------------------


def _make_game_state(
    graph: Graph,
    models: dict[str, ModelState],
    invalid_move_penalty: int = 1,
    timeout: float = 5.0,
    max_turns: int = 100,
    completion_bonus_multiplier: float = 1.0,
) -> GameState:
    """Build a GameState from graph and models dict."""
    config = GameConfig(
        graph_config=GraphConfig(),
        num_models=max(2, len(models)),
        max_turns=max_turns,
        move_timeout_seconds=timeout,
        invalid_move_penalty=invalid_move_penalty,
        completion_bonus_multiplier=completion_bonus_multiplier,
    )
    return GameState(
        graph=graph,
        models=models,
        current_turn=0,
        max_turns=max_turns,
        config=config,
    )


# ---------------------------------------------------------------------------
# Property 16: Invalid move penalty
# **Validates: Requirements 4.3**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=5000)
@given(
    graph_data=arbitrary_graph_with_model_and_invalid_target(),
    penalty=st.integers(min_value=1, max_value=20),
)
def test_property_16_invalid_move_position_unchanged(
    graph_data: tuple[Graph, str, ModelState, str],
    penalty: int,
) -> None:
    """For any model that submits an invalid move, the model's position
    SHALL remain unchanged.

    **Validates: Requirements 4.3**
    """
    graph, model_id, model_state, invalid_target = graph_data
    original_position = model_state.current_node

    strategies = {model_id: FixedMoveStrategy(invalid_target)}
    game_state = _make_game_state(
        graph,
        {model_id: model_state},
        invalid_move_penalty=penalty,
    )

    result = execute_turn(game_state, strategies)

    assert result.models[model_id].current_node == original_position, (
        f"Model position changed from '{original_position}' to "
        f"'{result.models[model_id].current_node}' after invalid move to '{invalid_target}'"
    )


@settings(max_examples=100, deadline=5000)
@given(
    graph_data=arbitrary_graph_with_model_and_invalid_target(),
    penalty=st.integers(min_value=1, max_value=20),
)
def test_property_16_invalid_move_score_decreases_by_penalty(
    graph_data: tuple[Graph, str, ModelState, str],
    penalty: int,
) -> None:
    """For any model that submits an invalid move, the model's score
    SHALL decrease by the configured invalid_move_penalty.

    **Validates: Requirements 4.3**
    """
    graph, model_id, model_state, invalid_target = graph_data
    original_score = model_state.score

    strategies = {model_id: FixedMoveStrategy(invalid_target)}
    game_state = _make_game_state(
        graph,
        {model_id: model_state},
        invalid_move_penalty=penalty,
    )

    result = execute_turn(game_state, strategies)

    assert result.models[model_id].score == original_score - penalty, (
        f"Expected score {original_score - penalty} after penalty {penalty}, "
        f"got {result.models[model_id].score}"
    )


# ---------------------------------------------------------------------------
# Property 17: Simultaneous move resolution is order-independent
# **Validates: Requirements 4.4**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=5000)
@given(data=arbitrary_graph_with_multiple_valid_moves())
def test_property_17_resolution_order_independent(
    data: tuple[Graph, list[ValidatedMove], dict[str, ModelState]],
) -> None:
    """For any set of valid moves in a turn, the resulting game state SHALL
    be the same regardless of the order in which moves are processed.

    **Validates: Requirements 4.4**
    """
    graph, moves, model_states = data

    # Get all permutations of the move order
    move_permutations = list(itertools.permutations(moves))

    # Resolve moves for the first permutation as the reference
    reference_game_state = _make_game_state(graph, copy.deepcopy(model_states))
    reference_result = resolve_moves(list(move_permutations[0]), reference_game_state)

    # Check every other permutation produces the same result
    for perm in move_permutations[1:]:
        perm_game_state = _make_game_state(graph, copy.deepcopy(model_states))
        perm_result = resolve_moves(list(perm), perm_game_state)

        # Compare final positions
        for model_id in model_states:
            assert reference_result.models[model_id].current_node == perm_result.models[model_id].current_node, (
                f"Model '{model_id}' position differs between permutations: "
                f"'{reference_result.models[model_id].current_node}' vs "
                f"'{perm_result.models[model_id].current_node}'"
            )
            # Compare final scores
            assert reference_result.models[model_id].score == perm_result.models[model_id].score, (
                f"Model '{model_id}' score differs between permutations: "
                f"{reference_result.models[model_id].score} vs "
                f"{perm_result.models[model_id].score}"
            )


# ---------------------------------------------------------------------------
# Property 18: Completion bonus calculation
# **Validates: Requirements 4.5, 5.3**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=5000)
@given(scenario=arbitrary_completion_scenario())
def test_property_18_completion_bonus_calculation(
    scenario: tuple[ModelState, int, int, float],
) -> None:
    """For any model that reaches the Ending_Node, the model's score SHALL
    include a completion bonus equal to
    (max_turns - turns_taken) * completion_bonus_multiplier.

    **Validates: Requirements 4.5, 5.3**
    """
    model_state, turns_taken, max_turns, multiplier = scenario
    original_score = model_state.score

    result = apply_completion_bonus(model_state, turns_taken, max_turns, multiplier)

    expected_bonus = int((max_turns - turns_taken) * multiplier)
    expected_score = original_score + expected_bonus

    assert result.score == expected_score, (
        f"Expected score {expected_score} (original {original_score} + bonus {expected_bonus}), "
        f"got {result.score}. "
        f"max_turns={max_turns}, turns_taken={turns_taken}, multiplier={multiplier}"
    )


@settings(max_examples=100, deadline=5000)
@given(scenario=arbitrary_completion_scenario())
def test_property_18_completion_bonus_is_non_negative(
    scenario: tuple[ModelState, int, int, float],
) -> None:
    """For any valid completion scenario, the bonus SHALL be non-negative
    since turns_taken <= max_turns and multiplier > 0.

    **Validates: Requirements 4.5, 5.3**
    """
    model_state, turns_taken, max_turns, multiplier = scenario
    original_score = model_state.score

    apply_completion_bonus(model_state, turns_taken, max_turns, multiplier)

    bonus = model_state.score - original_score
    assert bonus >= 0, (
        f"Completion bonus should be non-negative, got {bonus}. "
        f"max_turns={max_turns}, turns_taken={turns_taken}, multiplier={multiplier}"
    )


# ---------------------------------------------------------------------------
# Property 19: Timeout results in no-op without penalty
# **Validates: Requirements 4.6**
# ---------------------------------------------------------------------------


@settings(max_examples=30, deadline=15000)
@given(
    initial_score=st.integers(min_value=0, max_value=500),
    node_idx=st.integers(min_value=0, max_value=2),
)
def test_property_19_timeout_position_unchanged(
    initial_score: int,
    node_idx: int,
) -> None:
    """For any model that times out during move computation, the model's
    position SHALL remain unchanged.

    **Validates: Requirements 4.6**
    """
    # Build a simple graph for the timeout test
    node_ids = ["A", "B", "C"]
    current_node = node_ids[node_idx]

    nodes = {
        "A": Node(id="A", node_type=NodeType.START),
        "B": Node(id="B", node_type=NodeType.NORMAL),
        "C": Node(id="C", node_type=NodeType.END),
    }
    edges = [
        Edge(source="A", target="B", cost=1, obstructed=False),
        Edge(source="B", target="C", cost=1, obstructed=False),
    ]
    adjacency: dict[str, list[tuple[str, Edge]]] = {
        "A": [("B", edges[0])],
        "B": [("A", edges[0]), ("C", edges[1])],
        "C": [("B", edges[1])],
    }
    graph = Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node="A",
        end_node="C",
    )

    model_id = "timeout_model"
    model_state = ModelState(
        model_id=model_id,
        strategy_name="test",
        current_node=current_node,
        score=initial_score,
        visited_nodes={current_node},
        visible_nodes=set(node_ids),
        visible_edges={("A", "B"), ("B", "C")},
    )

    # Use a very short timeout so the test completes quickly
    strategies = {model_id: TimeoutStrategy(delay=2.0)}
    game_state = _make_game_state(
        graph,
        {model_id: model_state},
        timeout=0.1,
    )

    result = execute_turn(game_state, strategies)

    assert result.models[model_id].current_node == current_node, (
        f"Model position changed from '{current_node}' to "
        f"'{result.models[model_id].current_node}' after timeout"
    )


@settings(max_examples=30, deadline=15000)
@given(
    initial_score=st.integers(min_value=0, max_value=500),
    node_idx=st.integers(min_value=0, max_value=2),
)
def test_property_19_timeout_score_unchanged(
    initial_score: int,
    node_idx: int,
) -> None:
    """For any model that times out during move computation, the model's
    score SHALL remain unchanged.

    **Validates: Requirements 4.6**
    """
    node_ids = ["A", "B", "C"]
    current_node = node_ids[node_idx]

    nodes = {
        "A": Node(id="A", node_type=NodeType.START),
        "B": Node(id="B", node_type=NodeType.NORMAL),
        "C": Node(id="C", node_type=NodeType.END),
    }
    edges = [
        Edge(source="A", target="B", cost=1, obstructed=False),
        Edge(source="B", target="C", cost=1, obstructed=False),
    ]
    adjacency: dict[str, list[tuple[str, Edge]]] = {
        "A": [("B", edges[0])],
        "B": [("A", edges[0]), ("C", edges[1])],
        "C": [("B", edges[1])],
    }
    graph = Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node="A",
        end_node="C",
    )

    model_id = "timeout_model"
    model_state = ModelState(
        model_id=model_id,
        strategy_name="test",
        current_node=current_node,
        score=initial_score,
        visited_nodes={current_node},
        visible_nodes=set(node_ids),
        visible_edges={("A", "B"), ("B", "C")},
    )

    strategies = {model_id: TimeoutStrategy(delay=2.0)}
    game_state = _make_game_state(
        graph,
        {model_id: model_state},
        timeout=0.1,
    )

    result = execute_turn(game_state, strategies)

    assert result.models[model_id].score == initial_score, (
        f"Model score changed from {initial_score} to "
        f"{result.models[model_id].score} after timeout"
    )
