"""Tests for the game_reporter module."""

from __future__ import annotations

import json

from graph_model_arena.game_reporter import (
    deserialize_game,
    generate_summary,
    serialize_game,
)
from graph_model_arena.models import (
    Edge,
    EventType,
    GameConfig,
    GameEvent,
    GameState,
    Graph,
    GraphConfig,
    ModelState,
    Node,
    NodeType,
    TerminationCause,
)


def _make_test_graph() -> Graph:
    """Create a simple test graph with a few nodes and edges."""
    nodes = {
        "n0": Node(id="n0", node_type=NodeType.START),
        "n1": Node(id="n1", node_type=NodeType.CHECKPOINT),
        "n2": Node(id="n2", node_type=NodeType.POINTS, point_value=5),
        "n3": Node(id="n3", node_type=NodeType.TRAP),
        "n4": Node(id="n4", node_type=NodeType.END),
    }
    edges = [
        Edge(source="n0", target="n1", cost=2),
        Edge(source="n1", target="n2", cost=3),
        Edge(source="n2", target="n4", cost=1),
        Edge(source="n0", target="n3", cost=1),
        Edge(source="n3", target="n4", cost=4, obstructed=True),
    ]
    adjacency: dict[str, list[tuple[str, Edge]]] = {nid: [] for nid in nodes}
    for edge in edges:
        adjacency[edge.source].append((edge.target, edge))
        adjacency[edge.target].append((edge.source, edge))

    return Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node="n0",
        end_node="n4",
    )


def _make_test_game_state() -> GameState:
    """Create a test game state with two models that have finished."""
    graph = _make_test_graph()
    models = {
        "model_a": ModelState(
            model_id="model_a",
            strategy_name="RandomWalker",
            current_node="n4",
            score=15,
            has_finished=True,
            active_checkpoint="n1",
            visited_nodes={"n0", "n1", "n2", "n4"},
            visible_nodes={"n0", "n1", "n2", "n3", "n4"},
            visible_edges={("n0", "n1"), ("n1", "n2"), ("n2", "n4")},
            turns_taken=3,
            trap_deaths=0,
        ),
        "model_b": ModelState(
            model_id="model_b",
            strategy_name="ShortestPath",
            current_node="n2",
            score=5,
            has_finished=False,
            active_checkpoint=None,
            visited_nodes={"n0", "n3", "n2"},
            visible_nodes={"n0", "n1", "n3", "n2"},
            visible_edges={("n0", "n3"), ("n0", "n1")},
            turns_taken=10,
            trap_deaths=1,
        ),
    }
    config = GameConfig(
        graph_config=GraphConfig(num_nodes=20),
        num_models=2,
        max_turns=10,
    )
    event_log = [
        GameEvent(
            turn=1,
            model_id="model_a",
            event_type=EventType.MOVE,
            details={"from": "n0", "to": "n1"},
        ),
        GameEvent(
            turn=2,
            model_id="model_b",
            event_type=EventType.TRAP_RESPAWN_START,
            details={"trap_node": "n3"},
        ),
    ]
    return GameState(
        graph=graph,
        models=models,
        current_turn=10,
        max_turns=10,
        config=config,
        event_log=event_log,
    )


class TestGenerateSummary:
    """Tests for generate_summary."""

    def test_summary_contains_full_graph(self):
        game_state = _make_test_game_state()
        summary = generate_summary(game_state)
        assert summary.graph is game_state.graph

    def test_summary_contains_rankings(self):
        game_state = _make_test_game_state()
        summary = generate_summary(game_state)
        assert len(summary.rankings) == 2
        # model_a has higher score (15 vs 5)
        assert summary.rankings[0].model_id == "model_a"
        assert summary.rankings[0].rank == 1
        assert summary.rankings[0].final_score == 15
        assert summary.rankings[1].model_id == "model_b"
        assert summary.rankings[1].rank == 2

    def test_summary_contains_total_turns(self):
        game_state = _make_test_game_state()
        summary = generate_summary(game_state)
        assert summary.total_turns == 10

    def test_summary_contains_graph_stats(self):
        game_state = _make_test_game_state()
        summary = generate_summary(game_state)
        stats = summary.graph_stats
        assert stats["num_nodes"] == 5
        assert stats["num_edges"] == 5
        assert stats["num_obstructed_edges"] == 1
        assert stats["num_start"] == 1
        assert stats["num_end"] == 1
        assert stats["num_trap"] == 1
        assert stats["num_checkpoint"] == 1
        assert stats["num_points"] == 1

    def test_summary_contains_event_log(self):
        game_state = _make_test_game_state()
        summary = generate_summary(game_state)
        assert len(summary.event_log) == 2
        assert summary.event_log[0].event_type == EventType.MOVE
        assert summary.event_log[1].event_type == EventType.TRAP_RESPAWN_START

    def test_summary_ranking_termination_cause(self):
        game_state = _make_test_game_state()
        summary = generate_summary(game_state)
        assert summary.rankings[0].cause_of_termination == TerminationCause.FINISHED
        assert summary.rankings[1].cause_of_termination == TerminationCause.TURN_LIMIT


class TestSerializeGame:
    """Tests for serialize_game."""

    def test_serialize_returns_dict(self):
        game_state = _make_test_game_state()
        result = serialize_game(game_state)
        assert isinstance(result, dict)

    def test_serialize_is_json_serializable(self):
        game_state = _make_test_game_state()
        result = serialize_game(game_state)
        # Should not raise
        json_str = json.dumps(result)
        assert isinstance(json_str, str)

    def test_serialize_contains_graph(self):
        game_state = _make_test_game_state()
        result = serialize_game(game_state)
        assert "graph" in result
        assert "nodes" in result["graph"]
        assert "edges" in result["graph"]
        assert result["graph"]["start_node"] == "n0"
        assert result["graph"]["end_node"] == "n4"

    def test_serialize_contains_models(self):
        game_state = _make_test_game_state()
        result = serialize_game(game_state)
        assert "models" in result
        assert "model_a" in result["models"]
        assert "model_b" in result["models"]
        assert result["models"]["model_a"]["score"] == 15

    def test_serialize_contains_events(self):
        game_state = _make_test_game_state()
        result = serialize_game(game_state)
        assert "event_log" in result
        assert len(result["event_log"]) == 2
        assert result["event_log"][0]["event_type"] == "MOVE"

    def test_serialize_converts_sets_to_lists(self):
        game_state = _make_test_game_state()
        result = serialize_game(game_state)
        model_a = result["models"]["model_a"]
        assert isinstance(model_a["visited_nodes"], list)
        assert isinstance(model_a["visible_nodes"], list)
        assert isinstance(model_a["visible_edges"], list)

    def test_serialize_converts_enums_to_names(self):
        game_state = _make_test_game_state()
        result = serialize_game(game_state)
        # Node types should be enum names
        node_n0 = result["graph"]["nodes"]["n0"]
        assert node_n0["node_type"] == "START"
        # Event types should be enum names
        assert result["event_log"][0]["event_type"] == "MOVE"

    def test_serialize_contains_config(self):
        game_state = _make_test_game_state()
        result = serialize_game(game_state)
        assert "config" in result
        assert result["config"]["num_models"] == 2
        assert result["config"]["max_turns"] == 10
        assert result["config"]["graph_config"]["num_nodes"] == 20


class TestDeserializeGame:
    """Tests for deserialize_game."""

    def test_round_trip_preserves_graph(self):
        game_state = _make_test_game_state()
        serialized = serialize_game(game_state)
        restored = deserialize_game(serialized)

        assert len(restored.graph.nodes) == len(game_state.graph.nodes)
        assert restored.graph.start_node == game_state.graph.start_node
        assert restored.graph.end_node == game_state.graph.end_node
        for node_id, node in game_state.graph.nodes.items():
            assert restored.graph.nodes[node_id].node_type == node.node_type
            assert restored.graph.nodes[node_id].point_value == node.point_value

    def test_round_trip_preserves_edges(self):
        game_state = _make_test_game_state()
        serialized = serialize_game(game_state)
        restored = deserialize_game(serialized)

        assert len(restored.graph.edges) == len(game_state.graph.edges)
        for orig, rest in zip(game_state.graph.edges, restored.graph.edges):
            assert orig.source == rest.source
            assert orig.target == rest.target
            assert orig.cost == rest.cost
            assert orig.obstructed == rest.obstructed

    def test_round_trip_preserves_model_state(self):
        game_state = _make_test_game_state()
        serialized = serialize_game(game_state)
        restored = deserialize_game(serialized)

        for model_id in game_state.models:
            orig = game_state.models[model_id]
            rest = restored.models[model_id]
            assert rest.model_id == orig.model_id
            assert rest.strategy_name == orig.strategy_name
            assert rest.current_node == orig.current_node
            assert rest.score == orig.score
            assert rest.has_finished == orig.has_finished
            assert rest.active_checkpoint == orig.active_checkpoint
            assert rest.visited_nodes == orig.visited_nodes
            assert rest.visible_nodes == orig.visible_nodes
            assert rest.visible_edges == orig.visible_edges
            assert rest.turns_taken == orig.turns_taken
            assert rest.trap_deaths == orig.trap_deaths

    def test_round_trip_preserves_config(self):
        game_state = _make_test_game_state()
        serialized = serialize_game(game_state)
        restored = deserialize_game(serialized)

        assert restored.config.num_models == game_state.config.num_models
        assert restored.config.max_turns == game_state.config.max_turns
        assert (
            restored.config.graph_config.num_nodes
            == game_state.config.graph_config.num_nodes
        )

    def test_round_trip_preserves_event_log(self):
        game_state = _make_test_game_state()
        serialized = serialize_game(game_state)
        restored = deserialize_game(serialized)

        assert len(restored.event_log) == len(game_state.event_log)
        for orig, rest in zip(game_state.event_log, restored.event_log):
            assert rest.turn == orig.turn
            assert rest.model_id == orig.model_id
            assert rest.event_type == orig.event_type
            assert rest.details == orig.details

    def test_round_trip_preserves_turn_info(self):
        game_state = _make_test_game_state()
        serialized = serialize_game(game_state)
        restored = deserialize_game(serialized)

        assert restored.current_turn == game_state.current_turn
        assert restored.max_turns == game_state.max_turns

    def test_round_trip_rebuilds_adjacency(self):
        game_state = _make_test_game_state()
        serialized = serialize_game(game_state)
        restored = deserialize_game(serialized)

        # Adjacency should be rebuilt from edges
        assert len(restored.graph.adjacency) == len(game_state.graph.nodes)
        # n0 should have neighbors n1 and n3
        n0_neighbors = {n for n, _ in restored.graph.adjacency["n0"]}
        assert "n1" in n0_neighbors
        assert "n3" in n0_neighbors

    def test_deserialize_from_json_string(self):
        """Verify the full pipeline: serialize -> JSON string -> parse -> deserialize."""
        game_state = _make_test_game_state()
        serialized = serialize_game(game_state)
        json_str = json.dumps(serialized)
        parsed = json.loads(json_str)
        restored = deserialize_game(parsed)

        assert restored.current_turn == game_state.current_turn
        assert len(restored.models) == len(game_state.models)
