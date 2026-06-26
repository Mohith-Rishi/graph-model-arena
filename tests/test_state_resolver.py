"""Unit tests for the State Resolver."""

from __future__ import annotations

from graph_model_arena.models import (
    Edge,
    EventType,
    GameConfig,
    GameState,
    Graph,
    GraphConfig,
    ModelState,
    Node,
    NodeType,
    ValidatedMove,
)
from graph_model_arena.state_resolver import resolve_moves


def _make_graph() -> Graph:
    """Create a test graph with various node types."""
    nodes = {
        "start": Node(id="start", node_type=NodeType.START),
        "end": Node(id="end", node_type=NodeType.END),
        "trap": Node(id="trap", node_type=NodeType.TRAP),
        "checkpoint": Node(id="checkpoint", node_type=NodeType.CHECKPOINT),
        "points": Node(id="points", node_type=NodeType.POINTS, point_value=5),
        "normal_a": Node(id="normal_a", node_type=NodeType.NORMAL),
        "normal_b": Node(id="normal_b", node_type=NodeType.NORMAL),
    }
    edges = [
        Edge(source="start", target="normal_a", cost=1),
        Edge(source="start", target="normal_b", cost=1),
        Edge(source="start", target="checkpoint", cost=1),
        Edge(source="normal_a", target="trap", cost=1),
        Edge(source="normal_a", target="points", cost=1),
        Edge(source="normal_b", target="end", cost=1),
        Edge(source="checkpoint", target="trap", cost=1),
        Edge(source="points", target="end", cost=1),
    ]
    adjacency: dict[str, list[tuple[str, Edge]]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, []).append((edge.target, edge))
        adjacency.setdefault(edge.target, []).append((edge.source, edge))

    return Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node="start",
        end_node="end",
    )


def _make_game_state(num_models: int = 2) -> GameState:
    """Create a game state with models at start."""
    graph = _make_graph()
    models: dict[str, ModelState] = {}

    for i in range(num_models):
        model_id = f"model_{i}"
        models[model_id] = ModelState(
            model_id=model_id,
            strategy_name="test_strategy",
            current_node="start",
            score=50,
            visited_nodes={"start"},
            visible_nodes={"start", "normal_a", "normal_b", "checkpoint"},
            visible_edges={
                ("normal_a", "start"),
                ("normal_b", "start"),
                ("checkpoint", "start"),
            },
        )

    config = GameConfig(
        graph_config=GraphConfig(map_reveal_depth=2),
        death_penalty=10,
        trap_respawn_penalty=5,
    )

    return GameState(
        graph=graph,
        models=models,
        current_turn=1,
        max_turns=100,
        config=config,
    )


class TestBasicMovement:
    def test_single_model_moves_to_target(self):
        game_state = _make_game_state(num_models=1)
        moves = [ValidatedMove(model_id="model_0", target_node="normal_a", valid=True)]

        result = resolve_moves(moves, game_state)

        assert result.models["model_0"].current_node == "normal_a"

    def test_model_position_updated_to_target(self):
        game_state = _make_game_state(num_models=1)
        moves = [ValidatedMove(model_id="model_0", target_node="normal_b", valid=True)]

        result = resolve_moves(moves, game_state)

        assert result.models["model_0"].current_node == "normal_b"

    def test_target_node_added_to_visited(self):
        game_state = _make_game_state(num_models=1)
        moves = [ValidatedMove(model_id="model_0", target_node="normal_a", valid=True)]

        result = resolve_moves(moves, game_state)

        assert "normal_a" in result.models["model_0"].visited_nodes

    def test_multiple_models_move_simultaneously(self):
        game_state = _make_game_state(num_models=2)
        moves = [
            ValidatedMove(model_id="model_0", target_node="normal_a", valid=True),
            ValidatedMove(model_id="model_1", target_node="normal_b", valid=True),
        ]

        result = resolve_moves(moves, game_state)

        assert result.models["model_0"].current_node == "normal_a"
        assert result.models["model_1"].current_node == "normal_b"

    def test_invalid_move_is_skipped(self):
        game_state = _make_game_state(num_models=1)
        moves = [
            ValidatedMove(
                model_id="model_0", target_node="normal_a", valid=False, reason="invalid"
            )
        ]

        result = resolve_moves(moves, game_state)

        # Model should remain at start
        assert result.models["model_0"].current_node == "start"


class TestMoveEvents:
    def test_move_event_logged(self):
        game_state = _make_game_state(num_models=1)
        moves = [ValidatedMove(model_id="model_0", target_node="normal_a", valid=True)]

        resolve_moves(moves, game_state)

        move_events = [
            e for e in game_state.event_log if e.event_type == EventType.MOVE
        ]
        assert len(move_events) == 1
        assert move_events[0].model_id == "model_0"
        assert move_events[0].details["target_node"] == "normal_a"

    def test_no_event_for_invalid_move(self):
        game_state = _make_game_state(num_models=1)
        moves = [
            ValidatedMove(
                model_id="model_0", target_node="normal_a", valid=False, reason="bad"
            )
        ]

        resolve_moves(moves, game_state)

        assert len(game_state.event_log) == 0


class TestNodeEffects:
    def test_checkpoint_node_sets_active_checkpoint(self):
        game_state = _make_game_state(num_models=1)
        moves = [ValidatedMove(model_id="model_0", target_node="checkpoint", valid=True)]

        result = resolve_moves(moves, game_state)

        assert result.models["model_0"].active_checkpoint == "checkpoint"

    def test_points_node_adds_score_on_first_visit(self):
        game_state = _make_game_state(num_models=1)
        moves = [ValidatedMove(model_id="model_0", target_node="points", valid=True)]

        result = resolve_moves(moves, game_state)

        # Original score was 50, points node has value 5
        assert result.models["model_0"].score == 55

    def test_points_node_no_score_on_revisit(self):
        game_state = _make_game_state(num_models=1)
        # Mark points as already visited
        game_state.models["model_0"].visited_nodes.add("points")
        moves = [ValidatedMove(model_id="model_0", target_node="points", valid=True)]

        result = resolve_moves(moves, game_state)

        assert result.models["model_0"].score == 50


class TestTrapRespawn:
    def test_trap_without_checkpoint_respawns_at_start(self):
        game_state = _make_game_state(num_models=1)
        game_state.models["model_0"].current_node = "normal_a"
        game_state.models["model_0"].active_checkpoint = None
        moves = [ValidatedMove(model_id="model_0", target_node="trap", valid=True)]

        result = resolve_moves(moves, game_state)

        assert result.models["model_0"].current_node == "start"

    def test_trap_without_checkpoint_applies_death_penalty(self):
        game_state = _make_game_state(num_models=1)
        game_state.models["model_0"].current_node = "normal_a"
        game_state.models["model_0"].active_checkpoint = None
        moves = [ValidatedMove(model_id="model_0", target_node="trap", valid=True)]

        result = resolve_moves(moves, game_state)

        # Original score 50 - death_penalty 10 = 40
        assert result.models["model_0"].score == 40

    def test_trap_with_checkpoint_respawns_at_checkpoint(self):
        game_state = _make_game_state(num_models=1)
        game_state.models["model_0"].current_node = "normal_a"
        game_state.models["model_0"].active_checkpoint = "checkpoint"
        moves = [ValidatedMove(model_id="model_0", target_node="trap", valid=True)]

        result = resolve_moves(moves, game_state)

        assert result.models["model_0"].current_node == "checkpoint"

    def test_trap_with_checkpoint_applies_respawn_penalty(self):
        game_state = _make_game_state(num_models=1)
        game_state.models["model_0"].current_node = "normal_a"
        game_state.models["model_0"].active_checkpoint = "checkpoint"
        moves = [ValidatedMove(model_id="model_0", target_node="trap", valid=True)]

        result = resolve_moves(moves, game_state)

        # Original score 50 - trap_respawn_penalty 5 = 45
        assert result.models["model_0"].score == 45

    def test_trap_increments_trap_deaths(self):
        game_state = _make_game_state(num_models=1)
        game_state.models["model_0"].current_node = "normal_a"
        game_state.models["model_0"].active_checkpoint = None
        moves = [ValidatedMove(model_id="model_0", target_node="trap", valid=True)]

        result = resolve_moves(moves, game_state)

        assert result.models["model_0"].trap_deaths == 1


class TestVisibilityExpansion:
    def test_visibility_expanded_from_new_position(self):
        game_state = _make_game_state(num_models=1)
        model = game_state.models["model_0"]
        # Start with limited visibility
        model.visible_nodes = {"start"}
        model.visible_edges = set()
        moves = [ValidatedMove(model_id="model_0", target_node="normal_a", valid=True)]

        result = resolve_moves(moves, game_state)

        # After moving to normal_a, should see normal_a and its neighbors (start, trap, points)
        assert "normal_a" in result.models["model_0"].visible_nodes
        assert "trap" in result.models["model_0"].visible_nodes
        assert "points" in result.models["model_0"].visible_nodes
        assert "start" in result.models["model_0"].visible_nodes

    def test_visibility_expanded_from_respawn_position_after_trap(self):
        game_state = _make_game_state(num_models=1)
        model = game_state.models["model_0"]
        model.current_node = "normal_a"
        model.active_checkpoint = None
        model.visible_nodes = {"start", "normal_a", "trap"}
        model.visible_edges = set()
        moves = [ValidatedMove(model_id="model_0", target_node="trap", valid=True)]

        result = resolve_moves(moves, game_state)

        # After trap respawn at start, visibility expands from start
        # Start neighbors: normal_a, normal_b, checkpoint
        assert "start" in result.models["model_0"].visible_nodes
        assert "normal_a" in result.models["model_0"].visible_nodes
        assert "normal_b" in result.models["model_0"].visible_nodes
        assert "checkpoint" in result.models["model_0"].visible_nodes

    def test_visibility_expanded_from_checkpoint_after_trap(self):
        game_state = _make_game_state(num_models=1)
        model = game_state.models["model_0"]
        model.current_node = "normal_a"
        model.active_checkpoint = "checkpoint"
        model.visible_nodes = {"start", "normal_a", "checkpoint"}
        model.visible_edges = set()
        moves = [ValidatedMove(model_id="model_0", target_node="trap", valid=True)]

        result = resolve_moves(moves, game_state)

        # After trap respawn at checkpoint, visibility expands from checkpoint
        # Checkpoint neighbors: start, trap
        assert "checkpoint" in result.models["model_0"].visible_nodes
        assert "start" in result.models["model_0"].visible_nodes
        assert "trap" in result.models["model_0"].visible_nodes


class TestSimultaneousResolution:
    def test_multiple_models_effects_processed_independently(self):
        game_state = _make_game_state(num_models=2)
        moves = [
            ValidatedMove(model_id="model_0", target_node="checkpoint", valid=True),
            ValidatedMove(model_id="model_1", target_node="points", valid=True),
        ]

        result = resolve_moves(moves, game_state)

        # model_0 gets checkpoint activated
        assert result.models["model_0"].active_checkpoint == "checkpoint"
        assert result.models["model_0"].score == 50  # unchanged

        # model_1 gets points
        assert result.models["model_1"].score == 55
        assert result.models["model_1"].active_checkpoint is None

    def test_empty_moves_list_returns_unchanged_state(self):
        game_state = _make_game_state(num_models=1)
        moves: list[ValidatedMove] = []

        result = resolve_moves(moves, game_state)

        assert result.models["model_0"].current_node == "start"
        assert result.models["model_0"].score == 50

    def test_mixed_valid_and_invalid_moves(self):
        game_state = _make_game_state(num_models=2)
        moves = [
            ValidatedMove(model_id="model_0", target_node="normal_a", valid=True),
            ValidatedMove(
                model_id="model_1", target_node="end", valid=False, reason="not adjacent"
            ),
        ]

        result = resolve_moves(moves, game_state)

        # model_0 moved
        assert result.models["model_0"].current_node == "normal_a"
        # model_1 stayed
        assert result.models["model_1"].current_node == "start"
