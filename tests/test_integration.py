"""Integration tests for Graph Model Arena — end-to-end game scenarios.

Validates: Requirements 2.1, 2.2, 7.3, 7.4

These tests exercise the full system from config → create_game → start_game → summary,
using deterministic custom strategies and hand-crafted graphs to verify specific behaviors.
"""

from __future__ import annotations

from graph_model_arena.game_engine import create_game, start_game
from graph_model_arena.game_reporter import generate_summary
from graph_model_arena.model_interface import ModelStrategy
from graph_model_arena.models import (
    Edge,
    EventType,
    GameConfig,
    GameState,
    GameSummary,
    Graph,
    GraphConfig,
    ModelState,
    ModelView,
    Node,
    NodeType,
    RankedModel,
    TerminationCause,
)


# ---------------------------------------------------------------------------
# Custom test strategies
# ---------------------------------------------------------------------------


class StepByStepStrategy(ModelStrategy):
    """Follows a pre-defined path step by step."""

    def __init__(self, path: list[str]):
        self._path = list(path)
        self._index = 0

    def decide_move(self, state: ModelView) -> str:
        if self._index < len(self._path):
            target = self._path[self._index]
            self._index += 1
            return target
        # Stay at current node once path exhausted
        return state.current_node


class StayStrategy(ModelStrategy):
    """Always returns the current node (triggers invalid move penalty)."""

    def decide_move(self, state: ModelView) -> str:
        return state.current_node


# ---------------------------------------------------------------------------
# Graph factory helpers
# ---------------------------------------------------------------------------


def _make_graph_with_trap_no_checkpoint() -> Graph:
    """Graph for testing trap without checkpoint:

    n0 (START) -- n1 (NORMAL) -- n2 (TRAP) -- n3 (NORMAL) -- n4 (END)

    Model walks n0 → n1 → n2 (trap) → respawns at n0.
    All edges cost 1.
    """
    nodes = {
        "n0": Node(id="n0", node_type=NodeType.START),
        "n1": Node(id="n1", node_type=NodeType.NORMAL),
        "n2": Node(id="n2", node_type=NodeType.TRAP),
        "n3": Node(id="n3", node_type=NodeType.NORMAL),
        "n4": Node(id="n4", node_type=NodeType.END),
    }
    edges = [
        Edge(source="n0", target="n1", cost=1),
        Edge(source="n1", target="n2", cost=1),
        Edge(source="n2", target="n3", cost=1),
        Edge(source="n3", target="n4", cost=1),
    ]
    adjacency: dict[str, list[tuple[str, Edge]]] = {
        "n0": [("n1", edges[0])],
        "n1": [("n0", edges[0]), ("n2", edges[1])],
        "n2": [("n1", edges[1]), ("n3", edges[2])],
        "n3": [("n2", edges[2]), ("n4", edges[3])],
        "n4": [("n3", edges[3])],
    }
    return Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node="n0",
        end_node="n4",
    )


def _make_graph_with_checkpoint_then_trap() -> Graph:
    """Graph for testing trap with active checkpoint:

    n0 (START) -- n1 (CHECKPOINT) -- n2 (TRAP) -- n3 (END)

    Model walks n0 → n1 (checkpoint activated) → n2 (trap) → respawns at n1.
    All edges cost 1.
    """
    nodes = {
        "n0": Node(id="n0", node_type=NodeType.START),
        "n1": Node(id="n1", node_type=NodeType.CHECKPOINT),
        "n2": Node(id="n2", node_type=NodeType.TRAP),
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


def _make_graph_for_turn_limit() -> Graph:
    """Graph for testing turn limit and proximity scoring:

    n0 (START) -- n1 -- n2 -- n3 -- n4 (END)

    All edges cost 2. With max_turns=3:
    - Model A follows path n1, n2, n3 (ends at n3, distance 2 from end)
    - Model B follows path n1, n0, n1 (ends at n1, distance 6 from end)
    """
    nodes = {
        "n0": Node(id="n0", node_type=NodeType.START),
        "n1": Node(id="n1", node_type=NodeType.NORMAL),
        "n2": Node(id="n2", node_type=NodeType.NORMAL),
        "n3": Node(id="n3", node_type=NodeType.NORMAL),
        "n4": Node(id="n4", node_type=NodeType.END),
    }
    edges = [
        Edge(source="n0", target="n1", cost=2),
        Edge(source="n1", target="n2", cost=2),
        Edge(source="n2", target="n3", cost=2),
        Edge(source="n3", target="n4", cost=2),
    ]
    adjacency: dict[str, list[tuple[str, Edge]]] = {
        "n0": [("n1", edges[0])],
        "n1": [("n0", edges[0]), ("n2", edges[1])],
        "n2": [("n1", edges[1]), ("n3", edges[2])],
        "n3": [("n2", edges[2]), ("n4", edges[3])],
        "n4": [("n3", edges[3])],
    }
    return Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node="n0",
        end_node="n4",
    )


# ---------------------------------------------------------------------------
# Helper to set up a game state from a hand-crafted graph
# ---------------------------------------------------------------------------


def _init_game_state(
    graph: Graph,
    strategies: dict[str, ModelStrategy],
    max_turns: int = 50,
    death_penalty: int = 10,
    trap_respawn_penalty: int = 5,
    completion_bonus_multiplier: float = 1.0,
) -> GameState:
    """Build an initialized GameState with models at start and visibility set up."""
    config = GameConfig(
        max_turns=max_turns,
        death_penalty=death_penalty,
        trap_respawn_penalty=trap_respawn_penalty,
        completion_bonus_multiplier=completion_bonus_multiplier,
    )

    models: dict[str, ModelState] = {}
    for model_id, strategy in strategies.items():
        ms = ModelState(
            model_id=model_id,
            strategy_name=type(strategy).__name__,
            current_node=graph.start_node,
        )
        # Initialize visibility: start node + immediate neighbors
        ms.visible_nodes.add(graph.start_node)
        for neighbor_id, edge in graph.adjacency.get(graph.start_node, []):
            ms.visible_nodes.add(neighbor_id)
            ms.visible_edges.add((edge.source, edge.target))
        models[model_id] = ms

    return GameState(
        graph=graph,
        models=models,
        current_turn=0,
        max_turns=max_turns,
        config=config,
        event_log=[],
    )


# ---------------------------------------------------------------------------
# Integration Test: Full game with minimum config
# ---------------------------------------------------------------------------


class TestFullGameMinConfig:
    """Run a full game with minimum config and verify summary structure."""

    def test_full_game_with_generated_graph(self):
        """Run a complete game using graph generator (20 nodes, 2 models, low turns).

        Verifies:
        - Game completes without error
        - Summary has required structure (graph, rankings, graph_stats, event_log)
        - Rankings contain all models with valid fields
        """
        config = GameConfig(
            graph_config=GraphConfig(
                num_nodes=20,
                edge_density=0.3,
                trap_probability=0.05,
                checkpoint_probability=0.05,
                points_probability=0.1,
                obstacle_density=0.05,
            ),
            num_models=2,
            max_turns=15,
            completion_bonus_multiplier=1.0,
            death_penalty=10,
            trap_respawn_penalty=5,
        )

        strategies = {
            "model_a": StayStrategy(),
            "model_b": StayStrategy(),
        }

        # Create and run game
        game_state = create_game(config, strategies)
        result = start_game(game_state, strategies)

        # Generate summary
        summary = generate_summary(result)

        # Verify summary structure
        assert isinstance(summary, GameSummary)
        assert summary.graph is not None
        assert len(summary.graph.nodes) == 20
        assert summary.total_turns > 0
        assert isinstance(summary.graph_stats, dict)
        assert "num_nodes" in summary.graph_stats
        assert "num_edges" in summary.graph_stats
        assert isinstance(summary.event_log, list)

        # Verify rankings
        assert len(summary.rankings) == 2
        for ranked in summary.rankings:
            assert isinstance(ranked, RankedModel)
            assert ranked.model_id in ("model_a", "model_b")
            assert ranked.rank in (1, 2)
            assert isinstance(ranked.final_score, int)
            assert isinstance(ranked.turns_taken, int)
            assert isinstance(ranked.nodes_visited, int)
            assert ranked.cause_of_termination in (
                TerminationCause.FINISHED,
                TerminationCause.TURN_LIMIT,
            )
            assert isinstance(ranked.strategy_name, str)

    def test_full_game_both_models_reach_end(self):
        """Run a game with a simple graph where both models can reach the end.

        Verifies Requirements 7.3: game ends when all models reach end.
        """
        graph = Graph(
            nodes={
                "s": Node(id="s", node_type=NodeType.START),
                "a": Node(id="a", node_type=NodeType.NORMAL),
                "e": Node(id="e", node_type=NodeType.END),
            },
            edges=[
                Edge(source="s", target="a", cost=1),
                Edge(source="a", target="e", cost=1),
            ],
            adjacency={
                "s": [("a", Edge(source="s", target="a", cost=1))],
                "a": [
                    ("s", Edge(source="s", target="a", cost=1)),
                    ("e", Edge(source="a", target="e", cost=1)),
                ],
                "e": [("a", Edge(source="a", target="e", cost=1))],
            },
            start_node="s",
            end_node="e",
        )

        strategies = {
            "m1": StepByStepStrategy(["a", "e"]),
            "m2": StepByStepStrategy(["a", "e"]),
        }

        game_state = _init_game_state(
            graph, strategies, max_turns=20, completion_bonus_multiplier=2.0
        )
        result = start_game(game_state, strategies)

        # Both models should have finished
        assert result.models["m1"].has_finished is True
        assert result.models["m2"].has_finished is True

        # Game should end at turn 2 (both take 2 steps)
        assert result.current_turn == 2

        # Summary should show all models finished
        summary = generate_summary(result)
        for ranked in summary.rankings:
            assert ranked.cause_of_termination == TerminationCause.FINISHED


# ---------------------------------------------------------------------------
# Integration Test: Trap without checkpoint → respawn at Starting_Node
# ---------------------------------------------------------------------------


class TestTrapWithoutCheckpoint:
    """Validates Requirement 2.1: trap respawn at Starting_Node without checkpoint."""

    def test_trap_respawns_model_at_start(self):
        """Model hits a trap without checkpoint and respawns at start.

        Scenario:
        - Graph: n0 (START) → n1 → n2 (TRAP) → n3 → n4 (END)
        - Model walks: n1, n2 (trap hit) → respawns at n0
        - Then walks: n1, n2, n3, n4 (second visit to n2 still triggers trap)
        - Actually, let's just verify the first trap hit respawns to start.

        We use a strategy that goes n1, n2 then after respawn goes n1, n2, n3, n4
        but for simplicity we just verify the state after the trap hit.
        """
        graph = _make_graph_with_trap_no_checkpoint()
        death_penalty = 10

        # Strategy: go n1, n2 (trap!), then after respawn: n1, n2, n3, n4
        # But n2 is a trap — model will be respawned at n0 each time it visits n2.
        # Let the model go: n1, n2 (respawn to n0)
        # After respawn the model is at n0. On next step it tries n3 which isn't adjacent to n0.
        # Actually let's just use 2 turns to see the trap effect.
        strategies = {
            "m1": StepByStepStrategy(["n1", "n2"]),
            "m2": StepByStepStrategy(["n1", "n1"]),  # just moves around
        }

        game_state = _init_game_state(
            graph,
            strategies,
            max_turns=5,
            death_penalty=death_penalty,
        )
        result = start_game(game_state, strategies)

        # m1 should have been respawned at start after hitting trap on turn 2
        # After 2 turns of moves + 3 more turns of staying/invalid moves
        # Let's check the event log for TRAP_RESPAWN_START
        trap_events = [
            e
            for e in result.event_log
            if e.event_type == EventType.TRAP_RESPAWN_START
            and e.model_id == "m1"
        ]
        assert len(trap_events) >= 1
        assert trap_events[0].details["trap_node"] == "n2"
        assert trap_events[0].details["respawn_node"] == "n0"
        assert trap_events[0].details["penalty"] == death_penalty

        # m1's score should reflect the death penalty
        assert result.models["m1"].score <= -death_penalty  # At least one penalty

    def test_trap_without_checkpoint_score_deduction(self):
        """Verify exact score deduction when model hits trap without checkpoint."""
        graph = _make_graph_with_trap_no_checkpoint()
        death_penalty = 15

        # Model goes: n1 (turn 1), n2/trap (turn 2)
        # After turn 2, model is back at n0 with -15 score
        strategies = {
            "m1": StepByStepStrategy(["n1", "n2"]),
            "m2": StepByStepStrategy(["n1", "n1"]),
        }

        game_state = _init_game_state(
            graph,
            strategies,
            max_turns=2,
            death_penalty=death_penalty,
        )
        result = start_game(game_state, strategies)

        # m1 hit the trap exactly once
        trap_events = [
            e
            for e in result.event_log
            if e.event_type == EventType.TRAP_RESPAWN_START
            and e.model_id == "m1"
        ]
        assert len(trap_events) == 1

        # After the trap, the model should be at start node
        # The proximity scoring at turn limit will add to score
        # But the base score from trap is -death_penalty
        # Model is at n0 after respawn, distance to n4 = 4 (via 4 cost-1 edges)
        # Proximity bonus: max(0, max_turns - distance) = max(0, 2 - 4) = 0
        assert result.models["m1"].score == -death_penalty


# ---------------------------------------------------------------------------
# Integration Test: Trap with checkpoint → respawn at checkpoint
# ---------------------------------------------------------------------------


class TestTrapWithCheckpoint:
    """Validates Requirement 2.2: trap respawn at checkpoint."""

    def test_trap_respawns_model_at_checkpoint(self):
        """Model activates checkpoint then hits trap, respawns at checkpoint.

        Scenario:
        - Graph: n0 (START) → n1 (CHECKPOINT) → n2 (TRAP) → n3 (END)
        - Model walks: n1 (checkpoint activated), n2 (trap hit) → respawns at n1
        """
        graph = _make_graph_with_checkpoint_then_trap()
        trap_respawn_penalty = 5

        # m1 goes: n1 (checkpoint), n2 (trap) → respawn at n1
        # m2 just follows along
        strategies = {
            "m1": StepByStepStrategy(["n1", "n2"]),
            "m2": StepByStepStrategy(["n1", "n1"]),
        }

        game_state = _init_game_state(
            graph,
            strategies,
            max_turns=5,
            trap_respawn_penalty=trap_respawn_penalty,
        )
        result = start_game(game_state, strategies)

        # Check for TRAP_RESPAWN_CHECKPOINT event
        trap_checkpoint_events = [
            e
            for e in result.event_log
            if e.event_type == EventType.TRAP_RESPAWN_CHECKPOINT
            and e.model_id == "m1"
        ]
        assert len(trap_checkpoint_events) >= 1
        assert trap_checkpoint_events[0].details["trap_node"] == "n2"
        assert trap_checkpoint_events[0].details["respawn_node"] == "n1"
        assert trap_checkpoint_events[0].details["penalty"] == trap_respawn_penalty

    def test_trap_with_checkpoint_exact_score(self):
        """Verify exact score after checkpoint activation then trap hit."""
        graph = _make_graph_with_checkpoint_then_trap()
        trap_respawn_penalty = 7

        # m1: n1 (checkpoint), n2 (trap → respawn at n1)
        strategies = {
            "m1": StepByStepStrategy(["n1", "n2"]),
            "m2": StepByStepStrategy(["n1", "n1"]),
        }

        game_state = _init_game_state(
            graph,
            strategies,
            max_turns=2,
            trap_respawn_penalty=trap_respawn_penalty,
        )
        result = start_game(game_state, strategies)

        # After trap, m1 is at n1 (checkpoint respawn)
        # Score should be -trap_respawn_penalty
        # Proximity: m1 at n1, distance to n3 = 2 (n1→n2 cost 1, n2→n3 cost 1)
        # But wait — n2 is a trap node, but path still goes through it for distance
        # calculation (Dijkstra considers all non-obstructed edges regardless of type)
        # Proximity bonus: max(0, 2 - 2) = 0
        assert result.models["m1"].score == -trap_respawn_penalty

    def test_checkpoint_activated_event_logged(self):
        """Verify CHECKPOINT_ACTIVATED event is logged."""
        graph = _make_graph_with_checkpoint_then_trap()

        strategies = {
            "m1": StepByStepStrategy(["n1", "n2"]),
            "m2": StepByStepStrategy(["n1", "n1"]),
        }

        game_state = _init_game_state(graph, strategies, max_turns=3)
        result = start_game(game_state, strategies)

        # Check checkpoint activation event
        checkpoint_events = [
            e
            for e in result.event_log
            if e.event_type == EventType.CHECKPOINT_ACTIVATED
            and e.model_id == "m1"
        ]
        assert len(checkpoint_events) >= 1
        assert checkpoint_events[0].details["checkpoint_node"] == "n1"


# ---------------------------------------------------------------------------
# Integration Test: Turn limit with proximity scoring
# ---------------------------------------------------------------------------


class TestTurnLimitProximityScoring:
    """Validates Requirement 7.4: turn limit ends game with proximity scoring."""

    def test_turn_limit_triggers_proximity_scoring(self):
        """Game hits turn limit, remaining models scored by proximity.

        Scenario:
        - Graph: n0 → n1 → n2 → n3 → n4 (END), all edges cost 2
        - max_turns = 3
        - Model A moves: n1, n2, n3 → ends at n3, distance=2 to end
        - Model B moves: n1, n0, n1 → ends at n1, distance=6 to end
        - Proximity bonus A: max(0, 3 - 2) = 1
        - Proximity bonus B: max(0, 3 - 6) = 0
        """
        graph = _make_graph_for_turn_limit()

        strategies = {
            "m_a": StepByStepStrategy(["n1", "n2", "n3"]),
            "m_b": StepByStepStrategy(["n1", "n0", "n1"]),
        }

        game_state = _init_game_state(
            graph,
            strategies,
            max_turns=3,
        )
        result = start_game(game_state, strategies)

        # Game should end at turn 3
        assert result.current_turn == 3

        # Neither model finished (n4 is the end node, nobody reached it)
        assert result.models["m_a"].has_finished is False
        assert result.models["m_b"].has_finished is False

        # Model A at n3, distance to n4 = 2, bonus = max(0, 3 - 2) = 1
        assert result.models["m_a"].score == 1

        # Model B at n1, distance to n4 = 6, bonus = max(0, 3 - 6) = 0
        assert result.models["m_b"].score == 0

    def test_turn_limit_event_logged(self):
        """Verify GAME_ENDED_BY_TURN_LIMIT event is logged."""
        graph = _make_graph_for_turn_limit()

        strategies = {
            "m_a": StepByStepStrategy(["n1", "n2", "n3"]),
            "m_b": StepByStepStrategy(["n1", "n0", "n1"]),
        }

        game_state = _init_game_state(graph, strategies, max_turns=3)
        result = start_game(game_state, strategies)

        turn_limit_events = [
            e
            for e in result.event_log
            if e.event_type == EventType.GAME_ENDED_BY_TURN_LIMIT
        ]
        assert len(turn_limit_events) == 1
        assert turn_limit_events[0].details["max_turns"] == 3

    def test_turn_limit_summary_shows_turn_limit_termination(self):
        """Summary should indicate TURN_LIMIT as cause of termination."""
        graph = _make_graph_for_turn_limit()

        strategies = {
            "m_a": StepByStepStrategy(["n1", "n2", "n3"]),
            "m_b": StepByStepStrategy(["n1", "n0", "n1"]),
        }

        game_state = _init_game_state(graph, strategies, max_turns=3)
        result = start_game(game_state, strategies)
        summary = generate_summary(result)

        # Both models hit turn limit
        for ranked in summary.rankings:
            assert ranked.cause_of_termination == TerminationCause.TURN_LIMIT

        # Rankings should have model A first (higher proximity score)
        assert summary.rankings[0].model_id == "m_a"
        assert summary.rankings[0].final_score == 1
        assert summary.rankings[1].model_id == "m_b"
        assert summary.rankings[1].final_score == 0

    def test_mixed_finish_and_turn_limit(self):
        """One model finishes, the other hits turn limit.

        Graph: n0 (START) → n1 → n2 (END), all cost 1.
        max_turns = 4
        Model A goes: n1, n2 (finishes on turn 2)
        Model B goes: n1, n0, n1, n0 (never finishes)
        """
        nodes = {
            "n0": Node(id="n0", node_type=NodeType.START),
            "n1": Node(id="n1", node_type=NodeType.NORMAL),
            "n2": Node(id="n2", node_type=NodeType.END),
        }
        edges = [
            Edge(source="n0", target="n1", cost=1),
            Edge(source="n1", target="n2", cost=1),
        ]
        adjacency: dict[str, list[tuple[str, Edge]]] = {
            "n0": [("n1", edges[0])],
            "n1": [("n0", edges[0]), ("n2", edges[1])],
            "n2": [("n1", edges[1])],
        }
        graph = Graph(
            nodes=nodes,
            edges=edges,
            adjacency=adjacency,
            start_node="n0",
            end_node="n2",
        )

        strategies = {
            "fast": StepByStepStrategy(["n1", "n2"]),
            "slow": StepByStepStrategy(["n1", "n0", "n1", "n0"]),
        }

        game_state = _init_game_state(
            graph,
            strategies,
            max_turns=4,
            completion_bonus_multiplier=1.0,
        )
        result = start_game(game_state, strategies)

        # Fast model finished on turn 2
        assert result.models["fast"].has_finished is True
        assert result.models["fast"].turns_taken == 2
        # Completion bonus: (4 - 2) * 1.0 = 2
        assert result.models["fast"].score == 2

        # Slow model did not finish
        assert result.models["slow"].has_finished is False

        # Summary should reflect different termination causes
        summary = generate_summary(result)
        causes = {r.model_id: r.cause_of_termination for r in summary.rankings}
        assert causes["fast"] == TerminationCause.FINISHED
        assert causes["slow"] == TerminationCause.TURN_LIMIT
