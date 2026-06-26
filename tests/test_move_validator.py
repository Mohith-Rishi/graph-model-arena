"""Unit tests for the Move Validator."""

from __future__ import annotations

from graph_model_arena.models import (
    Edge,
    GameConfig,
    GameState,
    Graph,
    GraphConfig,
    ModelState,
    Node,
    NodeType,
)
from graph_model_arena.move_validator import validate_move


def _make_graph() -> Graph:
    """Create a simple test graph for move validation tests.

    Graph layout:
        A --1-- B --1-- C
        |               |
        2 (obstructed)  1
        |               |
        D --1-- E --1-- F
    """
    nodes = {
        "A": Node(id="A", node_type=NodeType.START),
        "B": Node(id="B", node_type=NodeType.NORMAL),
        "C": Node(id="C", node_type=NodeType.NORMAL),
        "D": Node(id="D", node_type=NodeType.NORMAL),
        "E": Node(id="E", node_type=NodeType.NORMAL),
        "F": Node(id="F", node_type=NodeType.END),
    }
    edges = [
        Edge(source="A", target="B", cost=1),
        Edge(source="B", target="C", cost=1),
        Edge(source="A", target="D", cost=2, obstructed=True),
        Edge(source="D", target="E", cost=1),
        Edge(source="E", target="F", cost=1),
        Edge(source="C", target="F", cost=1),
    ]
    adjacency: dict[str, list[tuple[str, Edge]]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, []).append((edge.target, edge))
        adjacency.setdefault(edge.target, []).append((edge.source, edge))

    return Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node="A",
        end_node="F",
    )


def _make_game_state() -> GameState:
    """Create a game state with a model at node A."""
    graph = _make_graph()
    model = ModelState(
        model_id="model_1",
        strategy_name="test_strategy",
        current_node="A",
        score=10,
        visited_nodes={"A"},
        visible_nodes={"A", "B", "D"},
        visible_edges={("A", "B"), ("A", "D")},
    )
    config = GameConfig(graph_config=GraphConfig())
    return GameState(
        graph=graph,
        models={"model_1": model},
        current_turn=1,
        max_turns=100,
        config=config,
    )


class TestAdjacencyCheck:
    """Tests for adjacency validation."""

    def test_valid_move_to_adjacent_node(self):
        game_state = _make_game_state()
        result = validate_move("model_1", "B", game_state)
        assert result.valid is True
        assert result.reason == ""

    def test_invalid_move_to_non_adjacent_node(self):
        game_state = _make_game_state()
        # C is not adjacent to A
        result = validate_move("model_1", "C", game_state)
        assert result.valid is False
        assert "not adjacent" in result.reason

    def test_invalid_move_to_non_existent_node(self):
        game_state = _make_game_state()
        result = validate_move("model_1", "Z", game_state)
        assert result.valid is False
        assert "not adjacent" in result.reason

    def test_invalid_move_to_same_node(self):
        game_state = _make_game_state()
        # Moving to the same node you're on is not adjacent (no self-loops)
        result = validate_move("model_1", "A", game_state)
        assert result.valid is False
        assert "not adjacent" in result.reason

    def test_valid_move_from_different_position(self):
        game_state = _make_game_state()
        # Move model to B, then validate move to C
        game_state.models["model_1"].current_node = "B"
        result = validate_move("model_1", "C", game_state)
        assert result.valid is True

    def test_valid_move_bidirectional(self):
        game_state = _make_game_state()
        # Move model to B, then validate move back to A
        game_state.models["model_1"].current_node = "B"
        result = validate_move("model_1", "A", game_state)
        assert result.valid is True


class TestObstructionCheck:
    """Tests for edge obstruction validation."""

    def test_invalid_move_on_obstructed_edge(self):
        game_state = _make_game_state()
        # Edge A->D is obstructed
        result = validate_move("model_1", "D", game_state)
        assert result.valid is False
        assert "obstructed" in result.reason

    def test_obstructed_edge_bidirectional(self):
        game_state = _make_game_state()
        # Edge is obstructed from both directions
        game_state.models["model_1"].current_node = "D"
        result = validate_move("model_1", "A", game_state)
        assert result.valid is False
        assert "obstructed" in result.reason

    def test_unobstructed_edge_is_valid(self):
        game_state = _make_game_state()
        # Edge A->B is not obstructed
        result = validate_move("model_1", "B", game_state)
        assert result.valid is True


class TestModelLookup:
    """Tests for model ID validation."""

    def test_invalid_model_id(self):
        game_state = _make_game_state()
        result = validate_move("nonexistent_model", "B", game_state)
        assert result.valid is False
        assert "not found" in result.reason

    def test_multiple_models(self):
        game_state = _make_game_state()
        # Add a second model at node E
        game_state.models["model_2"] = ModelState(
            model_id="model_2",
            strategy_name="test_strategy_2",
            current_node="E",
        )
        # Model 1 at A can move to B
        result = validate_move("model_1", "B", game_state)
        assert result.valid is True
        # Model 2 at E can move to F
        result = validate_move("model_2", "F", game_state)
        assert result.valid is True
        # Model 2 at E cannot move to A (not adjacent)
        result = validate_move("model_2", "A", game_state)
        assert result.valid is False


class TestEdgeCases:
    """Tests for edge cases in move validation."""

    def test_node_with_no_neighbors(self):
        """A node with no adjacency entry should reject all moves."""
        game_state = _make_game_state()
        # Add an isolated node and place model there
        game_state.graph.nodes["isolated"] = Node(id="isolated", node_type=NodeType.NORMAL)
        game_state.models["model_1"].current_node = "isolated"
        result = validate_move("model_1", "A", game_state)
        assert result.valid is False
        assert "not adjacent" in result.reason

    def test_move_result_reason_empty_when_valid(self):
        game_state = _make_game_state()
        result = validate_move("model_1", "B", game_state)
        assert result.valid is True
        assert result.reason == ""
