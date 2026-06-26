"""Unit tests for the 8 built-in model strategies.

Verifies each strategy:
- Subclasses ModelStrategy
- Returns a valid adjacent node from visible_edges
- Handles edge cases (no valid moves = stay at current node)
"""

from __future__ import annotations

import pytest

from graph_model_arena.model_interface import ModelStrategy
from graph_model_arena.models import ModelView, Node, NodeType
from graph_model_arena.strategies import (
    BalancedStrategist,
    CautiousNavigator,
    ClueSeeker,
    GreedyExplorer,
    RandomWalker,
    RiskTaker,
    ShortestPath,
    SprintRunner,
)


def _make_simple_state() -> ModelView:
    """Create a simple ModelView with a small graph for testing."""
    nodes = {
        "A": Node(id="A", node_type=NodeType.START),
        "B": Node(id="B", node_type=NodeType.NORMAL),
        "C": Node(id="C", node_type=NodeType.POINTS, point_value=5),
        "D": Node(id="D", node_type=NodeType.END),
    }
    # A--B--C--D, A is current
    edges = [
        ("A", "B", 1, False),
        ("B", "C", 2, False),
        ("C", "D", 1, False),
    ]
    return ModelView(
        current_node="A",
        visible_nodes=nodes,
        visible_edges=edges,
        current_score=0,
        turn_number=1,
        has_checkpoint=False,
        checkpoint_node=None,
    )


def _make_state_with_clues_and_maps() -> ModelView:
    """State with Clue and Map nodes adjacent."""
    nodes = {
        "A": Node(id="A", node_type=NodeType.NORMAL),
        "B": Node(id="B", node_type=NodeType.CLUE),
        "C": Node(id="C", node_type=NodeType.MAP),
        "D": Node(id="D", node_type=NodeType.END),
    }
    edges = [
        ("A", "B", 1, False),
        ("A", "C", 1, False),
        ("A", "D", 5, False),
    ]
    return ModelView(
        current_node="A",
        visible_nodes=nodes,
        visible_edges=edges,
        current_score=0,
        turn_number=1,
        has_checkpoint=False,
        checkpoint_node=None,
    )


def _make_state_with_checkpoint() -> ModelView:
    """State with a checkpoint node adjacent."""
    nodes = {
        "A": Node(id="A", node_type=NodeType.NORMAL),
        "B": Node(id="B", node_type=NodeType.CHECKPOINT),
        "C": Node(id="C", node_type=NodeType.TRAP),
    }
    edges = [
        ("A", "B", 1, False),
        ("A", "C", 1, False),
    ]
    return ModelView(
        current_node="A",
        visible_nodes=nodes,
        visible_edges=edges,
        current_score=0,
        turn_number=1,
        has_checkpoint=False,
        checkpoint_node=None,
    )


def _make_no_moves_state() -> ModelView:
    """State where the model has no valid moves (isolated node)."""
    nodes = {
        "A": Node(id="A", node_type=NodeType.START),
    }
    return ModelView(
        current_node="A",
        visible_nodes=nodes,
        visible_edges=[],
        current_score=0,
        turn_number=1,
        has_checkpoint=False,
        checkpoint_node=None,
    )


def _make_obstructed_state() -> ModelView:
    """State where some edges are obstructed."""
    nodes = {
        "A": Node(id="A", node_type=NodeType.START),
        "B": Node(id="B", node_type=NodeType.NORMAL),
        "C": Node(id="C", node_type=NodeType.NORMAL),
    }
    edges = [
        ("A", "B", 1, True),   # obstructed
        ("A", "C", 1, False),  # valid
    ]
    return ModelView(
        current_node="A",
        visible_nodes=nodes,
        visible_edges=edges,
        current_score=0,
        turn_number=1,
        has_checkpoint=False,
        checkpoint_node=None,
    )


def _get_valid_neighbors(state: ModelView) -> set[str]:
    """Helper to get the set of valid neighbor IDs from a state."""
    current = state.current_node
    neighbors = set()
    for source, target, cost, obstructed in state.visible_edges:
        if obstructed:
            continue
        if source == current:
            neighbors.add(target)
        elif target == current:
            neighbors.add(source)
    return neighbors


ALL_STRATEGIES = [
    RandomWalker,
    GreedyExplorer,
    ShortestPath,
    CautiousNavigator,
    RiskTaker,
    ClueSeeker,
    SprintRunner,
    BalancedStrategist,
]


class TestAllStrategiesSubclass:
    """All strategies must subclass ModelStrategy."""

    @pytest.mark.parametrize("strategy_cls", ALL_STRATEGIES)
    def test_is_model_strategy(self, strategy_cls):
        strategy = strategy_cls()
        assert isinstance(strategy, ModelStrategy)


class TestAllStrategiesHaveName:
    """All strategies must have a non-empty name."""

    @pytest.mark.parametrize("strategy_cls", ALL_STRATEGIES)
    def test_has_name(self, strategy_cls):
        strategy = strategy_cls()
        assert strategy.name
        assert isinstance(strategy.name, str)


class TestAllStrategiesReturnValidMove:
    """All strategies must return a valid adjacent node or stay at current."""

    @pytest.mark.parametrize("strategy_cls", ALL_STRATEGIES)
    def test_simple_graph(self, strategy_cls):
        strategy = strategy_cls()
        state = _make_simple_state()
        move = strategy.decide_move(state)
        valid_targets = _get_valid_neighbors(state) | {state.current_node}
        assert move in valid_targets

    @pytest.mark.parametrize("strategy_cls", ALL_STRATEGIES)
    def test_no_moves_stays_at_current(self, strategy_cls):
        strategy = strategy_cls()
        state = _make_no_moves_state()
        move = strategy.decide_move(state)
        assert move == state.current_node

    @pytest.mark.parametrize("strategy_cls", ALL_STRATEGIES)
    def test_obstructed_edges(self, strategy_cls):
        strategy = strategy_cls()
        state = _make_obstructed_state()
        move = strategy.decide_move(state)
        # Only C is reachable (B is obstructed)
        assert move in {"A", "C"}


class TestRandomWalker:
    def test_returns_neighbor(self):
        strategy = RandomWalker()
        state = _make_simple_state()
        # Run multiple times to verify randomness
        moves = {strategy.decide_move(state) for _ in range(50)}
        # Should always pick B since it's the only neighbor of A
        assert moves == {"B"}


class TestGreedyExplorer:
    def test_prefers_unvisited_points(self):
        """Should prefer unvisited Points_Nodes with higher value."""
        nodes = {
            "A": Node(id="A", node_type=NodeType.NORMAL),
            "B": Node(id="B", node_type=NodeType.POINTS, point_value=3),
            "C": Node(id="C", node_type=NodeType.POINTS, point_value=8),
        }
        edges = [("A", "B", 1, False), ("A", "C", 1, False)]
        state = ModelView(
            current_node="A",
            visible_nodes=nodes,
            visible_edges=edges,
            current_score=0,
            turn_number=1,
            has_checkpoint=False,
            checkpoint_node=None,
        )
        strategy = GreedyExplorer()
        move = strategy.decide_move(state)
        assert move == "C"  # higher value


class TestShortestPath:
    def test_follows_path_to_end(self):
        state = _make_simple_state()
        strategy = ShortestPath()
        move = strategy.decide_move(state)
        # From A, the shortest path to D is A->B->C->D, so first step is B
        assert move == "B"


class TestCautiousNavigator:
    def test_prefers_checkpoint_over_trap(self):
        state = _make_state_with_checkpoint()
        strategy = CautiousNavigator()
        move = strategy.decide_move(state)
        assert move == "B"  # checkpoint, not trap


class TestRiskTaker:
    def test_seeks_points_nodes(self):
        nodes = {
            "A": Node(id="A", node_type=NodeType.NORMAL),
            "B": Node(id="B", node_type=NodeType.TRAP),
            "C": Node(id="C", node_type=NodeType.POINTS, point_value=10),
        }
        edges = [("A", "B", 1, False), ("A", "C", 1, False)]
        state = ModelView(
            current_node="A",
            visible_nodes=nodes,
            visible_edges=edges,
            current_score=0,
            turn_number=1,
            has_checkpoint=False,
            checkpoint_node=None,
        )
        strategy = RiskTaker()
        move = strategy.decide_move(state)
        assert move == "C"  # prefers points node


class TestClueSeeker:
    def test_prefers_map_over_clue(self):
        state = _make_state_with_clues_and_maps()
        strategy = ClueSeeker()
        move = strategy.decide_move(state)
        assert move == "C"  # MAP node preferred over CLUE

    def test_prefers_info_over_end(self):
        state = _make_state_with_clues_and_maps()
        strategy = ClueSeeker()
        move = strategy.decide_move(state)
        assert move in {"B", "C"}  # Info nodes over End


class TestSprintRunner:
    def test_beelines_to_end(self):
        state = _make_simple_state()
        strategy = SprintRunner()
        move = strategy.decide_move(state)
        # From A, path to D is A->B->C->D, first step is B
        assert move == "B"


class TestBalancedStrategist:
    def test_early_game_explores(self):
        """In early turns, should explore (prefer unvisited)."""
        state = _make_simple_state()
        state = ModelView(
            current_node=state.current_node,
            visible_nodes=state.visible_nodes,
            visible_edges=state.visible_edges,
            current_score=0,
            turn_number=1,
            has_checkpoint=False,
            checkpoint_node=None,
        )
        strategy = BalancedStrategist()
        move = strategy.decide_move(state)
        # B is the only neighbor, must pick it
        assert move == "B"

    def test_late_game_seeks_goal(self):
        """In late turns, should rush toward end."""
        state = ModelView(
            current_node="A",
            visible_nodes=_make_simple_state().visible_nodes,
            visible_edges=_make_simple_state().visible_edges,
            current_score=10,
            turn_number=50,
            has_checkpoint=False,
            checkpoint_node=None,
        )
        strategy = BalancedStrategist()
        move = strategy.decide_move(state)
        # From A to D: first step is B
        assert move == "B"
