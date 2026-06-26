"""Unit tests for game_engine module."""

from __future__ import annotations

import pytest

from graph_model_arena.game_engine import (
    _dijkstra_distance,
    create_game,
    start_game,
)
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


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class AlwaysMoveToStrategy:
    """Strategy that always moves to a fixed target node."""

    def __init__(self, target: str):
        self.target = target

    def decide_move(self, state: ModelView) -> str:
        return self.target


class StepByStepStrategy:
    """Strategy that follows a pre-defined path step by step."""

    def __init__(self, path: list[str]):
        self._path = list(path)
        self._index = 0

    def decide_move(self, state: ModelView) -> str:
        if self._index < len(self._path):
            target = self._path[self._index]
            self._index += 1
            return target
        # Stay in place if path exhausted (will be invalid move or no-op)
        return state.current_node


class StayInPlaceStrategy:
    """Strategy that always stays in place (submits current node, invalid)."""

    def decide_move(self, state: ModelView) -> str:
        return state.current_node


def _make_simple_graph() -> Graph:
    """Create a simple linear graph: n0 (START) -> n1 -> n2 -> n3 (END).

    All edges cost 1, no obstacles.
    """
    nodes = {
        "n0": Node(id="n0", node_type=NodeType.START),
        "n1": Node(id="n1", node_type=NodeType.NORMAL),
        "n2": Node(id="n2", node_type=NodeType.NORMAL),
        "n3": Node(id="n3", node_type=NodeType.END),
    }
    edges = [
        Edge(source="n0", target="n1", cost=1),
        Edge(source="n1", target="n2", cost=1),
        Edge(source="n2", target="n3", cost=1),
    ]
    adjacency: dict[str, list[tuple[str, Edge]]] = {
        "n0": [("n1", edges[0])],
        "n1": [("n0", edges[0]), ("n2", edges[1])],
        "n2": [("n1", edges[1]), ("n3", edges[2])],
        "n3": [("n2", edges[2])],
    }
    return Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node="n0",
        end_node="n3",
    )


def _make_branching_graph() -> Graph:
    """Create a branching graph for proximity testing:

    n0 (START) -- n1 -- n3 (END)
                   |
                  n2

    Edge costs: n0-n1=1, n1-n3=2, n1-n2=1, n2-n3 (no edge)
    """
    nodes = {
        "n0": Node(id="n0", node_type=NodeType.START),
        "n1": Node(id="n1", node_type=NodeType.NORMAL),
        "n2": Node(id="n2", node_type=NodeType.NORMAL),
        "n3": Node(id="n3", node_type=NodeType.END),
    }
    edges = [
        Edge(source="n0", target="n1", cost=1),
        Edge(source="n1", target="n2", cost=1),
        Edge(source="n1", target="n3", cost=2),
    ]
    adjacency: dict[str, list[tuple[str, Edge]]] = {
        "n0": [("n1", edges[0])],
        "n1": [("n0", edges[0]), ("n2", edges[1]), ("n3", edges[2])],
        "n2": [("n1", edges[1])],
        "n3": [("n1", edges[2])],
    }
    return Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node="n0",
        end_node="n3",
    )


# ---------------------------------------------------------------------------
# Tests for create_game
# ---------------------------------------------------------------------------


class TestCreateGame:
    """Tests for the create_game function."""

    def test_create_game_initializes_models_at_start(self):
        """Models should start at the start node with score 0."""
        config = GameConfig(
            graph_config=GraphConfig(num_nodes=20, edge_density=0.3),
            num_models=2,
            max_turns=50,
        )
        strategies = {
            "model_a": StayInPlaceStrategy(),
            "model_b": StayInPlaceStrategy(),
        }

        game_state = create_game(config, strategies)

        assert len(game_state.models) == 2
        for model in game_state.models.values():
            assert model.current_node == game_state.graph.start_node
            assert model.score == 0
            assert model.has_finished is False
            assert model.active_checkpoint is None

    def test_create_game_initializes_visibility(self):
        """Each model should see the start node and its neighbors."""
        config = GameConfig(
            graph_config=GraphConfig(num_nodes=20, edge_density=0.3),
            num_models=2,
            max_turns=50,
        )
        strategies = {
            "model_a": StayInPlaceStrategy(),
            "model_b": StayInPlaceStrategy(),
        }

        game_state = create_game(config, strategies)

        start = game_state.graph.start_node
        start_neighbors = {
            nb_id for nb_id, _ in game_state.graph.adjacency[start]
        }

        for model in game_state.models.values():
            assert start in model.visible_nodes
            for nb in start_neighbors:
                assert nb in model.visible_nodes

    def test_create_game_invalid_config_raises(self):
        """Invalid config should raise ValueError."""
        config = GameConfig(
            graph_config=GraphConfig(num_nodes=5),  # too few
            num_models=2,
            max_turns=50,
        )
        strategies = {"model_a": StayInPlaceStrategy(), "model_b": StayInPlaceStrategy()}

        with pytest.raises(ValueError):
            create_game(config, strategies)

    def test_create_game_strategy_name_recorded(self):
        """Strategy class name should be recorded in model state."""
        config = GameConfig(
            graph_config=GraphConfig(num_nodes=20),
            num_models=2,
            max_turns=50,
        )
        strategies = {
            "model_a": StayInPlaceStrategy(),
            "model_b": AlwaysMoveToStrategy("n0"),
        }

        game_state = create_game(config, strategies)

        assert game_state.models["model_a"].strategy_name == "StayInPlaceStrategy"
        assert game_state.models["model_b"].strategy_name == "AlwaysMoveToStrategy"


# ---------------------------------------------------------------------------
# Tests for start_game
# ---------------------------------------------------------------------------


class TestStartGame:
    """Tests for the start_game function."""

    def test_models_reach_end_game_finishes(self):
        """Game should end when all models reach the end node."""
        graph = _make_simple_graph()
        config = GameConfig(max_turns=20, completion_bonus_multiplier=1.0)

        # Both models follow path n1, n2, n3
        strategies = {
            "m1": StepByStepStrategy(["n1", "n2", "n3"]),
            "m2": StepByStepStrategy(["n1", "n2", "n3"]),
        }

        game_state = GameState(
            graph=graph,
            models={
                "m1": ModelState(
                    model_id="m1",
                    strategy_name="StepByStepStrategy",
                    current_node="n0",
                    visible_nodes={"n0", "n1"},
                    visible_edges={("n0", "n1")},
                ),
                "m2": ModelState(
                    model_id="m2",
                    strategy_name="StepByStepStrategy",
                    current_node="n0",
                    visible_nodes={"n0", "n1"},
                    visible_edges={("n0", "n1")},
                ),
            },
            current_turn=0,
            max_turns=20,
            config=config,
            event_log=[],
        )

        result = start_game(game_state, strategies)

        # Both models should have finished
        assert result.models["m1"].has_finished is True
        assert result.models["m2"].has_finished is True

        # Both took 3 turns to reach end
        assert result.models["m1"].turns_taken == 3
        assert result.models["m2"].turns_taken == 3

        # Completion bonus: (20 - 3) * 1.0 = 17
        assert result.models["m1"].score == 17
        assert result.models["m2"].score == 17

    def test_turn_limit_ends_game(self):
        """Game should end when max turns reached, scoring by proximity."""
        graph = _make_simple_graph()
        config = GameConfig(max_turns=2, completion_bonus_multiplier=1.0)

        # Models move toward end but won't reach it in 2 turns
        # m1: n0 -> n1 -> n2
        # m2: n0 -> n1 -> n0 (goes back — valid move)
        strategies = {
            "m1": StepByStepStrategy(["n1", "n2"]),
            "m2": StepByStepStrategy(["n1", "n0"]),
        }

        game_state = GameState(
            graph=graph,
            models={
                "m1": ModelState(
                    model_id="m1",
                    strategy_name="StepByStepStrategy",
                    current_node="n0",
                    visible_nodes={"n0", "n1"},
                    visible_edges={("n0", "n1")},
                ),
                "m2": ModelState(
                    model_id="m2",
                    strategy_name="StepByStepStrategy",
                    current_node="n0",
                    visible_nodes={"n0", "n1"},
                    visible_edges={("n0", "n1")},
                ),
            },
            current_turn=0,
            max_turns=2,
            config=config,
            event_log=[],
        )

        result = start_game(game_state, strategies)

        # Game should end at turn 2
        assert result.current_turn == 2

        # Neither model should be marked as finished
        assert result.models["m1"].has_finished is False
        assert result.models["m2"].has_finished is False

        # m1 at n2 (distance 1 to n3), proximity bonus = max(0, 2 - 1) = 1
        assert result.models["m1"].score == 1

        # m2 at n0 (distance 3 to n3), proximity bonus = max(0, 2 - 3) = 0
        assert result.models["m2"].score == 0

        # Check turn limit event was logged
        turn_limit_events = [
            e
            for e in result.event_log
            if e.event_type == EventType.GAME_ENDED_BY_TURN_LIMIT
        ]
        assert len(turn_limit_events) == 1

    def test_completion_bonus_calculation(self):
        """Completion bonus should be (max_turns - turns_taken) * multiplier."""
        graph = _make_simple_graph()
        config = GameConfig(max_turns=100, completion_bonus_multiplier=2.5)

        strategies = {
            "m1": StepByStepStrategy(["n1", "n2", "n3"]),
        }

        game_state = GameState(
            graph=graph,
            models={
                "m1": ModelState(
                    model_id="m1",
                    strategy_name="StepByStepStrategy",
                    current_node="n0",
                    visible_nodes={"n0", "n1"},
                    visible_edges={("n0", "n1")},
                ),
            },
            current_turn=0,
            max_turns=100,
            config=config,
            event_log=[],
        )

        result = start_game(game_state, strategies)

        # Model reaches end on turn 3
        # Bonus = (100 - 3) * 2.5 = 242.5 → int(242.5) = 242
        assert result.models["m1"].score == 242
        assert result.models["m1"].has_finished is True

    def test_game_finished_event_logged(self):
        """A GAME_FINISHED event should be logged for each model that finishes."""
        graph = _make_simple_graph()
        config = GameConfig(max_turns=20, completion_bonus_multiplier=1.0)

        strategies = {
            "m1": StepByStepStrategy(["n1", "n2", "n3"]),
        }

        game_state = GameState(
            graph=graph,
            models={
                "m1": ModelState(
                    model_id="m1",
                    strategy_name="StepByStepStrategy",
                    current_node="n0",
                    visible_nodes={"n0", "n1"},
                    visible_edges={("n0", "n1")},
                ),
            },
            current_turn=0,
            max_turns=20,
            config=config,
            event_log=[],
        )

        result = start_game(game_state, strategies)

        finished_events = [
            e
            for e in result.event_log
            if e.event_type == EventType.GAME_FINISHED
        ]
        assert len(finished_events) == 1
        assert finished_events[0].model_id == "m1"

    def test_one_model_finishes_early_other_hits_turn_limit(self):
        """One model finishes, the other hits turn limit."""
        graph = _make_simple_graph()
        config = GameConfig(max_turns=4, completion_bonus_multiplier=1.0)

        # m1 goes straight to end (3 turns)
        # m2 goes back and forth (won't reach end in 4 turns)
        strategies = {
            "m1": StepByStepStrategy(["n1", "n2", "n3"]),
            "m2": StepByStepStrategy(["n1", "n0", "n1", "n0"]),
        }

        game_state = GameState(
            graph=graph,
            models={
                "m1": ModelState(
                    model_id="m1",
                    strategy_name="StepByStepStrategy",
                    current_node="n0",
                    visible_nodes={"n0", "n1"},
                    visible_edges={("n0", "n1")},
                ),
                "m2": ModelState(
                    model_id="m2",
                    strategy_name="StepByStepStrategy",
                    current_node="n0",
                    visible_nodes={"n0", "n1"},
                    visible_edges={("n0", "n1")},
                ),
            },
            current_turn=0,
            max_turns=4,
            config=config,
            event_log=[],
        )

        result = start_game(game_state, strategies)

        # m1 finished on turn 3 with bonus (4 - 3) * 1.0 = 1
        assert result.models["m1"].has_finished is True
        assert result.models["m1"].turns_taken == 3
        assert result.models["m1"].score == 1

        # m2 did not finish, hit turn limit
        assert result.models["m2"].has_finished is False


# ---------------------------------------------------------------------------
# Tests for _dijkstra_distance
# ---------------------------------------------------------------------------


class TestDijkstraDistance:
    """Tests for the internal _dijkstra_distance helper."""

    def test_distance_to_self(self):
        """Distance from a node to itself should be 0."""
        graph = _make_simple_graph()
        assert _dijkstra_distance("n0", "n0", graph) == 0

    def test_simple_linear_path(self):
        """Distance along a linear graph with cost-1 edges."""
        graph = _make_simple_graph()
        assert _dijkstra_distance("n0", "n3", graph) == 3
        assert _dijkstra_distance("n2", "n3", graph) == 1

    def test_weighted_path(self):
        """Distance with varying edge costs."""
        graph = _make_branching_graph()
        # n0 -> n1 (cost 1) -> n3 (cost 2) = 3
        assert _dijkstra_distance("n0", "n3", graph) == 3
        # n2 -> n1 (cost 1) -> n3 (cost 2) = 3
        assert _dijkstra_distance("n2", "n3", graph) == 3

    def test_obstructed_edge_excluded(self):
        """Obstructed edges should not be traversed."""
        nodes = {
            "a": Node(id="a", node_type=NodeType.START),
            "b": Node(id="b", node_type=NodeType.NORMAL),
            "c": Node(id="c", node_type=NodeType.END),
        }
        # Direct a->c is obstructed; must go a->b->c
        edges = [
            Edge(source="a", target="c", cost=1, obstructed=True),
            Edge(source="a", target="b", cost=2),
            Edge(source="b", target="c", cost=3),
        ]
        adjacency: dict[str, list[tuple[str, Edge]]] = {
            "a": [("c", edges[0]), ("b", edges[1])],
            "b": [("a", edges[1]), ("c", edges[2])],
            "c": [("a", edges[0]), ("b", edges[2])],
        }
        graph = Graph(
            nodes=nodes,
            edges=edges,
            adjacency=adjacency,
            start_node="a",
            end_node="c",
        )
        # Shortest non-obstructed: a->b (2) + b->c (3) = 5
        assert _dijkstra_distance("a", "c", graph) == 5

    def test_unreachable_returns_none(self):
        """When target is unreachable, should return None."""
        nodes = {
            "a": Node(id="a", node_type=NodeType.START),
            "b": Node(id="b", node_type=NodeType.END),
        }
        # Only edge is obstructed
        edges = [Edge(source="a", target="b", cost=1, obstructed=True)]
        adjacency: dict[str, list[tuple[str, Edge]]] = {
            "a": [("b", edges[0])],
            "b": [("a", edges[0])],
        }
        graph = Graph(
            nodes=nodes,
            edges=edges,
            adjacency=adjacency,
            start_node="a",
            end_node="b",
        )
        assert _dijkstra_distance("a", "b", graph) is None
