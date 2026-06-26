"""Unit tests for the Node Effect Processor."""

from __future__ import annotations

import random

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
)
from graph_model_arena.node_effects import process_node_effect


def _make_graph() -> Graph:
    """Create a simple test graph with various node types."""
    nodes = {
        "start": Node(id="start", node_type=NodeType.START),
        "end": Node(id="end", node_type=NodeType.END),
        "trap": Node(id="trap", node_type=NodeType.TRAP),
        "checkpoint": Node(id="checkpoint", node_type=NodeType.CHECKPOINT),
        "clue": Node(id="clue", node_type=NodeType.CLUE),
        "map": Node(id="map", node_type=NodeType.MAP),
        "points": Node(id="points", node_type=NodeType.POINTS, point_value=5),
        "normal": Node(id="normal", node_type=NodeType.NORMAL),
    }
    edges = [
        Edge(source="start", target="trap", cost=1),
        Edge(source="start", target="checkpoint", cost=1),
        Edge(source="start", target="clue", cost=1),
        Edge(source="clue", target="normal", cost=1),
        Edge(source="clue", target="map", cost=1),
        Edge(source="map", target="points", cost=1),
        Edge(source="map", target="end", cost=1),
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


def _make_game_state(graph: Graph | None = None) -> GameState:
    """Create a game state with a single model for testing."""
    if graph is None:
        graph = _make_graph()

    model = ModelState(
        model_id="model_1",
        strategy_name="test_strategy",
        current_node="start",
        score=50,
        visited_nodes={"start"},
        visible_nodes={"start", "trap", "checkpoint", "clue"},
        visible_edges={("start", "trap"), ("checkpoint", "start"), ("clue", "start")},
    )

    config = GameConfig(
        graph_config=GraphConfig(map_reveal_depth=2),
        death_penalty=10,
        trap_respawn_penalty=5,
    )

    return GameState(
        graph=graph,
        models={"model_1": model},
        current_turn=3,
        max_turns=100,
        config=config,
    )


class TestCheckpointEffect:
    def test_checkpoint_sets_active_checkpoint(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        node = game_state.graph.nodes["checkpoint"]

        result = process_node_effect(model, node, game_state)

        assert result.active_checkpoint == "checkpoint"

    def test_checkpoint_logs_event(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        node = game_state.graph.nodes["checkpoint"]

        process_node_effect(model, node, game_state)

        events = [e for e in game_state.event_log if e.event_type == EventType.CHECKPOINT_ACTIVATED]
        assert len(events) == 1
        assert events[0].details["checkpoint_node"] == "checkpoint"

    def test_checkpoint_does_not_change_score(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        original_score = model.score
        node = game_state.graph.nodes["checkpoint"]

        result = process_node_effect(model, node, game_state)

        assert result.score == original_score


class TestTrapEffect:
    def test_trap_without_checkpoint_respawns_at_start(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        model.current_node = "trap"
        model.active_checkpoint = None
        node = game_state.graph.nodes["trap"]

        result = process_node_effect(model, node, game_state)

        assert result.current_node == "start"

    def test_trap_without_checkpoint_applies_death_penalty(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        model.current_node = "trap"
        model.active_checkpoint = None
        original_score = model.score
        node = game_state.graph.nodes["trap"]

        result = process_node_effect(model, node, game_state)

        assert result.score == original_score - game_state.config.death_penalty

    def test_trap_without_checkpoint_increments_trap_deaths(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        model.active_checkpoint = None
        node = game_state.graph.nodes["trap"]

        result = process_node_effect(model, node, game_state)

        assert result.trap_deaths == 1

    def test_trap_without_checkpoint_logs_respawn_start_event(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        model.active_checkpoint = None
        node = game_state.graph.nodes["trap"]

        process_node_effect(model, node, game_state)

        events = [e for e in game_state.event_log if e.event_type == EventType.TRAP_RESPAWN_START]
        assert len(events) == 1
        assert events[0].details["trap_node"] == "trap"
        assert events[0].details["respawn_node"] == "start"

    def test_trap_with_checkpoint_respawns_at_checkpoint(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        model.active_checkpoint = "checkpoint"
        model.current_node = "trap"
        node = game_state.graph.nodes["trap"]

        result = process_node_effect(model, node, game_state)

        assert result.current_node == "checkpoint"

    def test_trap_with_checkpoint_applies_respawn_penalty(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        model.active_checkpoint = "checkpoint"
        original_score = model.score
        node = game_state.graph.nodes["trap"]

        result = process_node_effect(model, node, game_state)

        assert result.score == original_score - game_state.config.trap_respawn_penalty

    def test_trap_with_checkpoint_increments_trap_deaths(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        model.active_checkpoint = "checkpoint"
        node = game_state.graph.nodes["trap"]

        result = process_node_effect(model, node, game_state)

        assert result.trap_deaths == 1

    def test_trap_with_checkpoint_logs_respawn_checkpoint_event(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        model.active_checkpoint = "checkpoint"
        node = game_state.graph.nodes["trap"]

        process_node_effect(model, node, game_state)

        events = [e for e in game_state.event_log if e.event_type == EventType.TRAP_RESPAWN_CHECKPOINT]
        assert len(events) == 1
        assert events[0].details["trap_node"] == "trap"
        assert events[0].details["respawn_node"] == "checkpoint"


class TestClueEffect:
    def test_clue_reveals_one_neighbor(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        model.visible_nodes = {"start", "clue"}  # limited visibility
        node = game_state.graph.nodes["clue"]

        random.seed(42)
        process_node_effect(model, node, game_state)

        # Clue node has neighbors: start, normal, map
        # One should have been revealed (added to visible_nodes)
        clue_neighbors = {"start", "normal", "map"}
        revealed = model.visible_nodes - {"start", "clue"}
        # At least one neighbor revealed
        assert len(revealed) >= 1
        assert revealed.issubset(clue_neighbors)

    def test_clue_logs_event(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        node = game_state.graph.nodes["clue"]

        random.seed(42)
        process_node_effect(model, node, game_state)

        events = [e for e in game_state.event_log if e.event_type == EventType.CLUE_RECEIVED]
        assert len(events) == 1
        assert events[0].details["clue_node"] == "clue"
        assert "revealed_node" in events[0].details
        assert "revealed_type" in events[0].details

    def test_clue_does_not_change_score(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        original_score = model.score
        node = game_state.graph.nodes["clue"]

        process_node_effect(model, node, game_state)

        assert model.score == original_score


class TestMapEffect:
    def test_map_expands_visibility(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        model.visible_nodes = {"start", "map"}  # limited visibility
        node = game_state.graph.nodes["map"]

        process_node_effect(model, node, game_state)

        # Map node neighbors: clue, points, end (depth 1)
        # With depth 2: also clue's neighbors (start, normal) and points' neighbors (end), end's neighbors
        assert "points" in model.visible_nodes
        assert "end" in model.visible_nodes
        assert "clue" in model.visible_nodes

    def test_map_logs_event(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        node = game_state.graph.nodes["map"]

        process_node_effect(model, node, game_state)

        events = [e for e in game_state.event_log if e.event_type == EventType.MAP_REVEALED]
        assert len(events) == 1
        assert events[0].details["map_node"] == "map"
        assert events[0].details["depth"] == 2

    def test_map_does_not_change_score(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        original_score = model.score
        node = game_state.graph.nodes["map"]

        process_node_effect(model, node, game_state)

        assert model.score == original_score


class TestPointsEffect:
    def test_points_first_visit_adds_score(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        original_score = model.score
        # Ensure points node is not in visited set
        model.visited_nodes = {"start"}
        node = game_state.graph.nodes["points"]

        result = process_node_effect(model, node, game_state)

        assert result.score == original_score + 5

    def test_points_revisit_gives_zero(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        # Mark points as already visited
        model.visited_nodes = {"start", "points"}
        original_score = model.score
        node = game_state.graph.nodes["points"]

        result = process_node_effect(model, node, game_state)

        assert result.score == original_score

    def test_points_first_visit_logs_event(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        model.visited_nodes = {"start"}
        node = game_state.graph.nodes["points"]

        process_node_effect(model, node, game_state)

        events = [e for e in game_state.event_log if e.event_type == EventType.POINTS_COLLECTED]
        assert len(events) == 1
        assert events[0].details["points_awarded"] == 5

    def test_points_revisit_does_not_log_event(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        model.visited_nodes = {"start", "points"}
        node = game_state.graph.nodes["points"]

        process_node_effect(model, node, game_state)

        events = [e for e in game_state.event_log if e.event_type == EventType.POINTS_COLLECTED]
        assert len(events) == 0


class TestNormalNodeEffect:
    def test_normal_node_has_no_effect(self):
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        original_score = model.score
        original_checkpoint = model.active_checkpoint
        node = game_state.graph.nodes["normal"]

        result = process_node_effect(model, node, game_state)

        assert result.score == original_score
        assert result.active_checkpoint == original_checkpoint
        assert len(game_state.event_log) == 0


class TestEffectOrdering:
    def test_checkpoint_then_trap_on_same_processing(self):
        """If a node were somehow both checkpoint and trap, checkpoint processes first.
        In practice each node has one type, but this validates ordering."""
        game_state = _make_game_state()
        model = game_state.models["model_1"]
        # Test that a checkpoint node properly sets the checkpoint
        # and the next trap node uses it
        checkpoint_node = game_state.graph.nodes["checkpoint"]
        trap_node = game_state.graph.nodes["trap"]

        # First visit checkpoint
        model = process_node_effect(model, checkpoint_node, game_state)
        assert model.active_checkpoint == "checkpoint"

        # Then hit trap - should respawn at checkpoint
        original_score = model.score
        model = process_node_effect(model, trap_node, game_state)
        assert model.current_node == "checkpoint"
        assert model.score == original_score - game_state.config.trap_respawn_penalty
