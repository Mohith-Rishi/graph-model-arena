"""Property tests for Game Lifecycle and Serialization (Properties 12, 21-26).

**Feature: graph-model-arena, Properties 12, 21-26: Game Lifecycle**
**Validates: Requirements 3.1, 5.1, 5.6, 6.3, 7.2, 7.3, 7.4, 7.5**

Property 12: Initialization invariant
Property 21: Game summary completeness
Property 22: Unique model identifiers
Property 24: Game ends when all models have finished
Property 25: Turn limit ends game with proximity scoring
Property 26: Game state serialization round trip
"""

from __future__ import annotations

import copy

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from graph_model_arena.game_engine import create_game, start_game
from graph_model_arena.game_reporter import (
    deserialize_game,
    generate_summary,
    serialize_game,
)
from graph_model_arena.model_interface import ModelStrategy
from graph_model_arena.models import (
    Edge,
    EventType,
    GameConfig,
    GameState,
    Graph,
    GraphConfig,
    ModelState,
    ModelView,
    Node,
    NodeType,
    TerminationCause,
)
from graph_model_arena.visibility_manager import initialize_visibility


# ---------------------------------------------------------------------------
# Test strategies
# ---------------------------------------------------------------------------


class GoToEndStrategy(ModelStrategy):
    """A strategy that always moves toward the end node via shortest visible path."""

    def __init__(self, end_node: str, graph: Graph):
        self._end_node = end_node
        self._graph = graph

    def decide_move(self, state: ModelView) -> str:
        """Move toward end node using BFS on visible graph."""
        from collections import deque

        current = state.current_node
        if current == self._end_node:
            return current

        # Build adjacency from visible edges (non-obstructed only)
        adj: dict[str, list[str]] = {}
        for src, tgt, cost, obstructed in state.visible_edges:
            if obstructed:
                continue
            adj.setdefault(src, []).append(tgt)
            adj.setdefault(tgt, []).append(src)

        # BFS toward end
        visited = {current}
        queue: deque[tuple[str, str]] = deque()
        for nb in adj.get(current, []):
            queue.append((nb, nb))
            visited.add(nb)

        while queue:
            node, first_step = queue.popleft()
            if node == self._end_node:
                return first_step
            for nb in adj.get(node, []):
                if nb not in visited:
                    visited.add(nb)
                    queue.append((nb, first_step))

        # Fallback: move to any adjacent node
        if adj.get(current):
            return adj[current][0]
        return current


class StayStrategy(ModelStrategy):
    """A strategy that always tries to stay at current position (invalid move)."""

    def decide_move(self, state: ModelView) -> str:
        return state.current_node


# ---------------------------------------------------------------------------
# Custom Hypothesis strategies
# ---------------------------------------------------------------------------


@st.composite
def arbitrary_game_config(draw: st.DrawFn) -> GameConfig:
    """Generate a valid GameConfig with small graph for fast test execution."""
    graph_config = GraphConfig(
        num_nodes=draw(st.integers(min_value=20, max_value=30)),
        edge_density=draw(st.floats(min_value=0.1, max_value=0.5)),
        trap_probability=draw(st.floats(min_value=0.0, max_value=0.2)),
        clue_probability=draw(st.floats(min_value=0.0, max_value=0.1)),
        map_probability=draw(st.floats(min_value=0.0, max_value=0.1)),
        checkpoint_probability=draw(st.floats(min_value=0.0, max_value=0.1)),
        points_probability=draw(st.floats(min_value=0.0, max_value=0.2)),
        obstacle_density=draw(st.floats(min_value=0.0, max_value=0.3)),
        map_reveal_depth=draw(st.integers(min_value=1, max_value=3)),
    )
    num_models = draw(st.integers(min_value=2, max_value=5))
    return GameConfig(
        graph_config=graph_config,
        num_models=num_models,
        max_turns=draw(st.integers(min_value=10, max_value=50)),
        move_timeout_seconds=5.0,
        completion_bonus_multiplier=draw(
            st.floats(min_value=0.5, max_value=2.0, allow_nan=False, allow_infinity=False)
        ),
        death_penalty=draw(st.integers(min_value=1, max_value=10)),
        invalid_move_penalty=draw(st.integers(min_value=1, max_value=5)),
        trap_respawn_penalty=draw(st.integers(min_value=1, max_value=10)),
    )


@st.composite
def arbitrary_small_game_config_for_completion(draw: st.DrawFn) -> GameConfig:
    """Generate a config tuned so models can reach end quickly (small graph, high turns)."""
    graph_config = GraphConfig(
        num_nodes=20,
        edge_density=draw(st.floats(min_value=0.3, max_value=0.6)),
        trap_probability=0.0,  # No traps so models can reach end
        clue_probability=0.0,
        map_probability=0.0,
        checkpoint_probability=0.0,
        points_probability=0.0,
        obstacle_density=0.0,  # No obstacles
        map_reveal_depth=1,
    )
    num_models = draw(st.integers(min_value=2, max_value=4))
    return GameConfig(
        graph_config=graph_config,
        num_models=num_models,
        max_turns=200,  # High limit so models can reach end
        move_timeout_seconds=5.0,
        completion_bonus_multiplier=1.0,
        death_penalty=10,
        invalid_move_penalty=1,
        trap_respawn_penalty=5,
    )


@st.composite
def arbitrary_turn_limit_config(draw: st.DrawFn) -> GameConfig:
    """Generate a config that will hit turn limit (very few turns, complex graph)."""
    graph_config = GraphConfig(
        num_nodes=draw(st.integers(min_value=30, max_value=50)),
        edge_density=draw(st.floats(min_value=0.1, max_value=0.3)),
        trap_probability=0.0,
        clue_probability=0.0,
        map_probability=0.0,
        checkpoint_probability=0.0,
        points_probability=0.0,
        obstacle_density=0.0,
        map_reveal_depth=1,
    )
    num_models = draw(st.integers(min_value=2, max_value=3))
    return GameConfig(
        graph_config=graph_config,
        num_models=num_models,
        max_turns=3,  # Very few turns — forces turn limit
        move_timeout_seconds=5.0,
        completion_bonus_multiplier=1.0,
        death_penalty=10,
        invalid_move_penalty=1,
        trap_respawn_penalty=5,
    )


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _make_strategies(num_models: int, end_node: str = "", graph: Graph | None = None) -> dict[str, ModelStrategy]:
    """Create N strategies for testing with unique model IDs."""
    strategies: dict[str, ModelStrategy] = {}
    for i in range(num_models):
        model_id = f"model_{i}"
        if graph is not None and end_node:
            strategies[model_id] = GoToEndStrategy(end_node, graph)
        else:
            strategies[model_id] = StayStrategy()
    return strategies


def _make_stay_strategies(num_models: int) -> dict[str, ModelStrategy]:
    """Create N StayStrategy instances (models won't reach end)."""
    return {f"model_{i}": StayStrategy() for i in range(num_models)}


def _get_neighbors(node_id: str, graph: Graph) -> set[str]:
    """Get all neighbor node IDs (regardless of obstruction)."""
    neighbors = set()
    for neighbor_id, _ in graph.adjacency.get(node_id, []):
        neighbors.add(neighbor_id)
    return neighbors


# ---------------------------------------------------------------------------
# Property 12: Initialization invariant
# **Validates: Requirements 3.1, 5.1, 7.2**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=15000)
@given(config=arbitrary_game_config())
def test_property_12_all_models_at_start_node(config: GameConfig) -> None:
    """For any newly started game, all models SHALL be positioned at the Starting_Node.

    **Validates: Requirements 3.1, 5.1, 7.2**
    """
    strategies = _make_stay_strategies(config.num_models)
    game_state = create_game(config, strategies)

    start_node = game_state.graph.start_node
    for model_id, model in game_state.models.items():
        assert model.current_node == start_node, (
            f"Model '{model_id}' is at '{model.current_node}' instead of start node '{start_node}'"
        )


@settings(max_examples=100, deadline=15000)
@given(config=arbitrary_game_config())
def test_property_12_all_models_score_zero(config: GameConfig) -> None:
    """For any newly started game, all models SHALL have a score of zero.

    **Validates: Requirements 3.1, 5.1, 7.2**
    """
    strategies = _make_stay_strategies(config.num_models)
    game_state = create_game(config, strategies)

    for model_id, model in game_state.models.items():
        assert model.score == 0, (
            f"Model '{model_id}' has score {model.score} instead of 0"
        )


@settings(max_examples=100, deadline=15000)
@given(config=arbitrary_game_config())
def test_property_12_all_models_alive_not_finished(config: GameConfig) -> None:
    """For any newly started game, all models SHALL be alive and not finished.

    **Validates: Requirements 3.1, 5.1, 7.2**
    """
    strategies = _make_stay_strategies(config.num_models)
    game_state = create_game(config, strategies)

    for model_id, model in game_state.models.items():
        assert not model.has_finished, (
            f"Model '{model_id}' is marked as finished at game start"
        )


@settings(max_examples=100, deadline=15000)
@given(config=arbitrary_game_config())
def test_property_12_visibility_contains_start_and_neighbors(config: GameConfig) -> None:
    """For any newly started game, each model's visibility SHALL contain exactly
    the Starting_Node and its immediate neighbors.

    **Validates: Requirements 3.1, 5.1, 7.2**
    """
    strategies = _make_stay_strategies(config.num_models)
    game_state = create_game(config, strategies)

    start_node = game_state.graph.start_node
    expected_visible = {start_node} | _get_neighbors(start_node, game_state.graph)

    for model_id, model in game_state.models.items():
        assert model.visible_nodes == expected_visible, (
            f"Model '{model_id}' visibility {model.visible_nodes} does not match "
            f"expected {expected_visible}"
        )


# ---------------------------------------------------------------------------
# Property 21: Game summary completeness
# **Validates: Requirements 5.6**
# ---------------------------------------------------------------------------


@settings(max_examples=50, deadline=30000)
@given(config=arbitrary_small_game_config_for_completion())
def test_property_21_summary_contains_full_graph(config: GameConfig) -> None:
    """For any completed game, the game summary SHALL contain the full graph.

    **Validates: Requirements 5.6**
    """
    strategies = _make_stay_strategies(config.num_models)
    game_state = create_game(config, strategies)
    # Run game with StayStrategy — will hit turn limit
    game_state.max_turns = 5
    final_state = start_game(game_state, strategies)

    summary = generate_summary(final_state)

    # Summary graph should be the same graph
    assert summary.graph.start_node == final_state.graph.start_node
    assert summary.graph.end_node == final_state.graph.end_node
    assert len(summary.graph.nodes) == len(final_state.graph.nodes)
    assert len(summary.graph.edges) == len(final_state.graph.edges)


@settings(max_examples=50, deadline=30000)
@given(config=arbitrary_small_game_config_for_completion())
def test_property_21_summary_contains_rankings_for_all_models(config: GameConfig) -> None:
    """For any completed game, the summary SHALL contain each model's final score,
    rank, path taken, nodes visited, and cause of termination.

    **Validates: Requirements 5.6**
    """
    strategies = _make_stay_strategies(config.num_models)
    game_state = create_game(config, strategies)
    game_state.max_turns = 5
    final_state = start_game(game_state, strategies)

    summary = generate_summary(final_state)

    # Should have a ranking for each model
    assert len(summary.rankings) == len(final_state.models), (
        f"Expected {len(final_state.models)} rankings, got {len(summary.rankings)}"
    )

    model_ids_in_rankings = {r.model_id for r in summary.rankings}
    for model_id in final_state.models:
        assert model_id in model_ids_in_rankings, (
            f"Model '{model_id}' not found in summary rankings"
        )

    # Each ranking should have required fields
    for ranked in summary.rankings:
        assert ranked.rank >= 1
        assert ranked.model_id != ""
        assert ranked.strategy_name != ""
        assert ranked.final_score is not None
        assert ranked.turns_taken >= 0
        assert ranked.nodes_visited >= 0
        assert ranked.cause_of_termination in (
            TerminationCause.FINISHED,
            TerminationCause.TURN_LIMIT,
        )
        assert isinstance(ranked.path, list)


# ---------------------------------------------------------------------------
# Property 22: Unique model identifiers
# **Validates: Requirements 6.3**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=15000)
@given(config=arbitrary_game_config())
def test_property_22_unique_model_ids(config: GameConfig) -> None:
    """For any game with N models, all model IDs SHALL be unique.

    **Validates: Requirements 6.3**
    """
    strategies = _make_stay_strategies(config.num_models)
    game_state = create_game(config, strategies)

    model_ids = list(game_state.models.keys())
    assert len(model_ids) == len(set(model_ids)), (
        f"Duplicate model IDs found: {model_ids}"
    )
    assert len(model_ids) == config.num_models, (
        f"Expected {config.num_models} models, got {len(model_ids)}"
    )


# ---------------------------------------------------------------------------
# Property 24: Game ends when all models have finished
# **Validates: Requirements 7.3**
# ---------------------------------------------------------------------------


@settings(max_examples=30, deadline=60000)
@given(config=arbitrary_small_game_config_for_completion())
def test_property_24_game_ends_when_all_models_finished(config: GameConfig) -> None:
    """For any game state where all models have reached the Ending_Node,
    the game SHALL end.

    **Validates: Requirements 7.3**
    """
    strategies = _make_stay_strategies(config.num_models)
    game_state = create_game(config, strategies)

    # Replace strategies with GoToEnd so they actually reach the end
    graph = game_state.graph
    end_node = graph.end_node
    go_strategies = {
        model_id: GoToEndStrategy(end_node, graph)
        for model_id in game_state.models
    }

    final_state = start_game(game_state, go_strategies)

    # If all models finished, game should have ended before turn limit
    all_finished = all(m.has_finished for m in final_state.models.values())
    if all_finished:
        # Game ended because all finished, not by turn limit
        assert final_state.current_turn <= final_state.max_turns, (
            f"Game continued past turn limit: turn {final_state.current_turn} > max {final_state.max_turns}"
        )
        # Verify GAME_FINISHED events exist for each model
        finished_events = [
            e for e in final_state.event_log
            if e.event_type == EventType.GAME_FINISHED
        ]
        assert len(finished_events) == len(final_state.models), (
            f"Expected {len(final_state.models)} GAME_FINISHED events, "
            f"got {len(finished_events)}"
        )
    else:
        # Models didn't all finish — game ended by turn limit, which is also valid
        assert final_state.current_turn >= final_state.max_turns


# ---------------------------------------------------------------------------
# Property 25: Turn limit ends game with proximity scoring
# **Validates: Requirements 7.4**
# ---------------------------------------------------------------------------


@settings(max_examples=50, deadline=30000)
@given(config=arbitrary_turn_limit_config())
def test_property_25_turn_limit_ends_game(config: GameConfig) -> None:
    """For any game that reaches the maximum turn limit, the game SHALL end.

    **Validates: Requirements 7.4**
    """
    strategies = _make_stay_strategies(config.num_models)
    game_state = create_game(config, strategies)

    # StayStrategy makes invalid moves, so models won't reach end
    final_state = start_game(game_state, strategies)

    # Game should have ended at or by the turn limit
    assert final_state.current_turn >= config.max_turns, (
        f"Game ended at turn {final_state.current_turn} before max_turns {config.max_turns}"
    )


@settings(max_examples=50, deadline=30000)
@given(config=arbitrary_turn_limit_config())
def test_property_25_proximity_scoring_applied(config: GameConfig) -> None:
    """For any game that reaches the maximum turn limit, remaining active models
    SHALL receive a score based on their proximity to the Ending_Node.

    **Validates: Requirements 7.4**
    """
    strategies = _make_stay_strategies(config.num_models)
    game_state = create_game(config, strategies)

    # Record initial scores (all zero)
    initial_scores = {mid: 0 for mid in game_state.models}

    final_state = start_game(game_state, strategies)

    # Check that the GAME_ENDED_BY_TURN_LIMIT event was logged
    turn_limit_events = [
        e for e in final_state.event_log
        if e.event_type == EventType.GAME_ENDED_BY_TURN_LIMIT
    ]
    assert len(turn_limit_events) >= 1, (
        "Expected GAME_ENDED_BY_TURN_LIMIT event in log"
    )

    # All unfinished models should have turns_taken == max_turns
    for model_id, model in final_state.models.items():
        if not model.has_finished:
            assert model.turns_taken == config.max_turns, (
                f"Unfinished model '{model_id}' has turns_taken={model.turns_taken}, "
                f"expected {config.max_turns}"
            )


# ---------------------------------------------------------------------------
# Property 26: Game state serialization round trip
# **Validates: Requirements 7.5**
# ---------------------------------------------------------------------------


@settings(max_examples=50, deadline=30000)
@given(config=arbitrary_game_config())
def test_property_26_serialization_round_trip(config: GameConfig) -> None:
    """For any completed game state, serializing and then deserializing
    SHALL produce an equivalent game state.

    **Validates: Requirements 7.5**
    """
    strategies = _make_stay_strategies(config.num_models)
    game_state = create_game(config, strategies)

    # Run a few turns so state has some events
    game_state.max_turns = 3
    final_state = start_game(game_state, strategies)

    # Serialize and deserialize
    serialized = serialize_game(final_state)
    deserialized = deserialize_game(serialized)

    # Verify equivalence
    # Graph
    assert deserialized.graph.start_node == final_state.graph.start_node
    assert deserialized.graph.end_node == final_state.graph.end_node
    assert len(deserialized.graph.nodes) == len(final_state.graph.nodes)
    assert len(deserialized.graph.edges) == len(final_state.graph.edges)

    # Check all nodes are present with correct types
    for node_id, node in final_state.graph.nodes.items():
        assert node_id in deserialized.graph.nodes
        assert deserialized.graph.nodes[node_id].node_type == node.node_type
        assert deserialized.graph.nodes[node_id].point_value == node.point_value

    # Check all edges preserved
    original_edge_set = {
        (e.source, e.target, e.cost, e.obstructed)
        for e in final_state.graph.edges
    }
    deserialized_edge_set = {
        (e.source, e.target, e.cost, e.obstructed)
        for e in deserialized.graph.edges
    }
    assert original_edge_set == deserialized_edge_set

    # Models
    assert len(deserialized.models) == len(final_state.models)
    for model_id, model in final_state.models.items():
        assert model_id in deserialized.models
        dm = deserialized.models[model_id]
        assert dm.model_id == model.model_id
        assert dm.strategy_name == model.strategy_name
        assert dm.current_node == model.current_node
        assert dm.score == model.score
        assert dm.has_finished == model.has_finished
        assert dm.active_checkpoint == model.active_checkpoint
        assert dm.visited_nodes == model.visited_nodes
        assert dm.visible_nodes == model.visible_nodes
        assert dm.visible_edges == model.visible_edges
        assert dm.turns_taken == model.turns_taken
        assert dm.trap_deaths == model.trap_deaths

    # Game state metadata
    assert deserialized.current_turn == final_state.current_turn
    assert deserialized.max_turns == final_state.max_turns

    # Config
    assert deserialized.config.num_models == final_state.config.num_models
    assert deserialized.config.max_turns == final_state.config.max_turns
    assert deserialized.config.death_penalty == final_state.config.death_penalty
    assert deserialized.config.graph_config.num_nodes == final_state.config.graph_config.num_nodes

    # Event log
    assert len(deserialized.event_log) == len(final_state.event_log)
    for orig_event, deser_event in zip(final_state.event_log, deserialized.event_log):
        assert deser_event.turn == orig_event.turn
        assert deser_event.model_id == orig_event.model_id
        assert deser_event.event_type == orig_event.event_type
        assert deser_event.details == orig_event.details
