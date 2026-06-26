"""Unit tests for the Turn Manager."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

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
)
from graph_model_arena.model_interface import ModelStrategy
from graph_model_arena.turn_manager import (
    _build_model_view,
    execute_turn,
)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------


def _make_simple_graph() -> Graph:
    """Create a simple graph: A -- B -- C (linear, no obstacles)."""
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
    return Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node="A",
        end_node="C",
    )


def _make_game_state(
    model_positions: dict[str, str] | None = None,
    timeout: float = 5.0,
) -> GameState:
    """Create a game state with models at specified positions."""
    graph = _make_simple_graph()
    if model_positions is None:
        model_positions = {"model_1": "A", "model_2": "A"}

    models = {}
    for model_id, position in model_positions.items():
        models[model_id] = ModelState(
            model_id=model_id,
            strategy_name="test_strategy",
            current_node=position,
            visible_nodes={"A", "B", "C"},
            visible_edges={("A", "B"), ("B", "C")},
        )

    config = GameConfig(
        graph_config=GraphConfig(num_nodes=20),
        num_models=len(model_positions),
        max_turns=100,
        move_timeout_seconds=timeout,
        invalid_move_penalty=1,
    )

    return GameState(
        graph=graph,
        models=models,
        current_turn=0,
        max_turns=100,
        config=config,
    )


class SimpleStrategy:
    """A strategy that always returns a fixed target node."""

    def __init__(self, target: str):
        self.target = target

    def decide_move(self, state: ModelView) -> str:
        return self.target


class SlowStrategy:
    """A strategy that sleeps longer than the timeout."""

    def __init__(self, delay: float):
        self.delay = delay

    def decide_move(self, state: ModelView) -> str:
        time.sleep(self.delay)
        return "B"


class ExceptionStrategy:
    """A strategy that raises an exception."""

    def decide_move(self, state: ModelView) -> str:
        raise RuntimeError("Strategy crashed!")


# ---------------------------------------------------------------------------
# Tests: basic turn execution
# ---------------------------------------------------------------------------


class TestExecuteTurnBasic:
    """Test basic turn execution flow."""

    def test_valid_move_updates_position(self):
        """A valid move should update the model's position."""
        game_state = _make_game_state({"model_1": "A"})
        strategies = {"model_1": SimpleStrategy("B")}

        result = execute_turn(game_state, strategies)

        assert result.models["model_1"].current_node == "B"
        assert result.current_turn == 1

    def test_multiple_models_move_simultaneously(self):
        """Multiple models should all move in the same turn."""
        game_state = _make_game_state({"model_1": "A", "model_2": "B"})
        strategies = {
            "model_1": SimpleStrategy("B"),
            "model_2": SimpleStrategy("C"),
        }

        result = execute_turn(game_state, strategies)

        assert result.models["model_1"].current_node == "B"
        assert result.models["model_2"].current_node == "C"
        assert result.current_turn == 1

    def test_turn_counter_increments(self):
        """Turn counter should increment by 1 after execution."""
        game_state = _make_game_state({"model_1": "A"})
        game_state.current_turn = 5
        strategies = {"model_1": SimpleStrategy("B")}

        result = execute_turn(game_state, strategies)

        assert result.current_turn == 6

    def test_finished_models_are_skipped(self):
        """Models that have finished should not be asked for moves."""
        game_state = _make_game_state({"model_1": "A", "model_2": "B"})
        game_state.models["model_2"].has_finished = True
        strategies = {
            "model_1": SimpleStrategy("B"),
            "model_2": SimpleStrategy("C"),  # Should not be called
        }

        result = execute_turn(game_state, strategies)

        # model_1 moves, model_2 stays
        assert result.models["model_1"].current_node == "B"
        assert result.models["model_2"].current_node == "B"  # unchanged


# ---------------------------------------------------------------------------
# Tests: invalid move handling
# ---------------------------------------------------------------------------


class TestExecuteTurnInvalidMoves:
    """Test invalid move handling with penalties."""

    def test_invalid_move_keeps_position(self):
        """An invalid move should keep the model at its current position."""
        game_state = _make_game_state({"model_1": "A"})
        # "C" is not adjacent to "A"
        strategies = {"model_1": SimpleStrategy("C")}

        result = execute_turn(game_state, strategies)

        assert result.models["model_1"].current_node == "A"

    def test_invalid_move_applies_penalty(self):
        """An invalid move should deduct the configured penalty."""
        game_state = _make_game_state({"model_1": "A"})
        game_state.models["model_1"].score = 10
        strategies = {"model_1": SimpleStrategy("C")}

        result = execute_turn(game_state, strategies)

        assert result.models["model_1"].score == 9  # 10 - 1 penalty

    def test_invalid_move_logs_event(self):
        """An invalid move should log an INVALID_MOVE event."""
        game_state = _make_game_state({"model_1": "A"})
        strategies = {"model_1": SimpleStrategy("C")}

        result = execute_turn(game_state, strategies)

        invalid_events = [
            e
            for e in result.event_log
            if e.event_type == EventType.INVALID_MOVE
        ]
        assert len(invalid_events) == 1
        assert invalid_events[0].model_id == "model_1"
        assert invalid_events[0].details["target_node"] == "C"

    def test_obstructed_edge_is_invalid(self):
        """A move to an adjacent node via an obstructed edge is invalid."""
        game_state = _make_game_state({"model_1": "A"})
        # Obstruct the A->B edge
        game_state.graph.edges[0].obstructed = True
        strategies = {"model_1": SimpleStrategy("B")}

        result = execute_turn(game_state, strategies)

        assert result.models["model_1"].current_node == "A"
        assert result.models["model_1"].score == -1


# ---------------------------------------------------------------------------
# Tests: timeout handling
# ---------------------------------------------------------------------------


class TestExecuteTurnTimeout:
    """Test timeout handling for slow models."""

    def test_timeout_is_noop_no_penalty(self):
        """A timed-out model should stay in place with no penalty."""
        game_state = _make_game_state({"model_1": "A"}, timeout=0.1)
        game_state.models["model_1"].score = 10
        strategies = {"model_1": SlowStrategy(delay=2.0)}

        result = execute_turn(game_state, strategies)

        assert result.models["model_1"].current_node == "A"
        assert result.models["model_1"].score == 10  # No penalty

    def test_timeout_logs_event(self):
        """A timeout should log a TIMEOUT event."""
        game_state = _make_game_state({"model_1": "A"}, timeout=0.1)
        strategies = {"model_1": SlowStrategy(delay=2.0)}

        result = execute_turn(game_state, strategies)

        timeout_events = [
            e for e in result.event_log if e.event_type == EventType.TIMEOUT
        ]
        assert len(timeout_events) == 1
        assert timeout_events[0].model_id == "model_1"


# ---------------------------------------------------------------------------
# Tests: exception handling
# ---------------------------------------------------------------------------


class TestExecuteTurnExceptions:
    """Test model exception handling."""

    def test_exception_is_noop_no_penalty(self):
        """A model exception should result in no-op with no penalty."""
        game_state = _make_game_state({"model_1": "A"})
        game_state.models["model_1"].score = 10
        strategies = {"model_1": ExceptionStrategy()}

        result = execute_turn(game_state, strategies)

        assert result.models["model_1"].current_node == "A"
        assert result.models["model_1"].score == 10  # No penalty

    def test_exception_does_not_log_invalid_move(self):
        """A model exception should NOT log as an invalid move."""
        game_state = _make_game_state({"model_1": "A"})
        strategies = {"model_1": ExceptionStrategy()}

        result = execute_turn(game_state, strategies)

        invalid_events = [
            e
            for e in result.event_log
            if e.event_type == EventType.INVALID_MOVE
        ]
        assert len(invalid_events) == 0

    def test_exception_in_one_model_doesnt_affect_others(self):
        """An exception in one model should not prevent other models from moving."""
        game_state = _make_game_state({"model_1": "A", "model_2": "B"})
        strategies = {
            "model_1": ExceptionStrategy(),
            "model_2": SimpleStrategy("C"),
        }

        result = execute_turn(game_state, strategies)

        assert result.models["model_1"].current_node == "A"  # no-op
        assert result.models["model_2"].current_node == "C"  # moved


# ---------------------------------------------------------------------------
# Tests: ModelView construction
# ---------------------------------------------------------------------------


class TestBuildModelView:
    """Test the _build_model_view helper."""

    def test_model_view_contains_current_node(self):
        """ModelView should contain the model's current node."""
        game_state = _make_game_state({"model_1": "B"})

        view = _build_model_view("model_1", game_state)

        assert view.current_node == "B"

    def test_model_view_contains_score(self):
        """ModelView should reflect the model's current score."""
        game_state = _make_game_state({"model_1": "A"})
        game_state.models["model_1"].score = 42

        view = _build_model_view("model_1", game_state)

        assert view.current_score == 42

    def test_model_view_contains_turn_number(self):
        """ModelView should reflect the current turn number."""
        game_state = _make_game_state({"model_1": "A"})
        game_state.current_turn = 7

        view = _build_model_view("model_1", game_state)

        assert view.turn_number == 7

    def test_model_view_checkpoint_status(self):
        """ModelView should reflect checkpoint status."""
        game_state = _make_game_state({"model_1": "A"})
        game_state.models["model_1"].active_checkpoint = "B"

        view = _build_model_view("model_1", game_state)

        assert view.has_checkpoint is True
        assert view.checkpoint_node == "B"

    def test_model_view_no_checkpoint(self):
        """ModelView should show no checkpoint when none is active."""
        game_state = _make_game_state({"model_1": "A"})

        view = _build_model_view("model_1", game_state)

        assert view.has_checkpoint is False
        assert view.checkpoint_node is None

    def test_model_view_visible_edges(self):
        """ModelView should contain visible edges as tuples."""
        game_state = _make_game_state({"model_1": "A"})

        view = _build_model_view("model_1", game_state)

        # Should have edges that are within the model's visibility
        assert len(view.visible_edges) > 0
        # Each edge is (source, target, cost, obstructed)
        for edge in view.visible_edges:
            assert len(edge) == 4


# ---------------------------------------------------------------------------
# Tests: no strategy registered
# ---------------------------------------------------------------------------


class TestExecuteTurnNoStrategy:
    """Test behavior when no strategy is registered for a model."""

    def test_no_strategy_is_noop(self):
        """If no strategy is registered, model stays in place with no penalty."""
        game_state = _make_game_state({"model_1": "A"})
        game_state.models["model_1"].score = 5
        strategies: dict[str, ModelStrategy] = {}  # No strategies

        result = execute_turn(game_state, strategies)

        assert result.models["model_1"].current_node == "A"
        assert result.models["model_1"].score == 5
        assert result.current_turn == 1
