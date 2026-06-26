"""Game Reporter — produces structured output after game completion.

Responsibilities:
- Generate game summary with full graph, rankings, stats, and event log
- Serialize game state to a JSON-serializable dictionary
- Deserialize game state from a dictionary back to GameState
"""

from __future__ import annotations

from graph_model_arena.models import (
    Edge,
    EventType,
    GameConfig,
    GameEvent,
    GameState,
    GameSummary,
    Graph,
    GraphConfig,
    ModelState,
    Node,
    NodeType,
    RankedModel,
    TerminationCause,
)
from graph_model_arena.score_manager import compute_final_rankings


def generate_summary(game_state: GameState) -> GameSummary:
    """Generate a game summary from a completed game state.

    Includes the full graph, final rankings, graph statistics, and complete
    event log.

    Args:
        game_state: The final GameState after the game has ended.

    Returns:
        A GameSummary with all required information.
    """
    rankings = compute_final_rankings(list(game_state.models.values()))

    graph = game_state.graph
    graph_stats = _compute_graph_stats(graph)

    return GameSummary(
        graph=graph,
        rankings=rankings,
        total_turns=game_state.current_turn,
        graph_stats=graph_stats,
        event_log=list(game_state.event_log),
    )


def _compute_graph_stats(graph: Graph) -> dict:
    """Compute summary statistics about the graph."""
    node_type_counts: dict[str, int] = {}
    for node in graph.nodes.values():
        type_name = node.node_type.name.lower()
        node_type_counts[type_name] = node_type_counts.get(type_name, 0) + 1

    num_obstructed = sum(1 for e in graph.edges if e.obstructed)

    return {
        "num_nodes": len(graph.nodes),
        "num_edges": len(graph.edges),
        "num_obstructed_edges": num_obstructed,
        **{f"num_{k}": v for k, v in node_type_counts.items()},
    }


def serialize_game(game_state: GameState) -> dict:
    """Serialize a GameState to a JSON-serializable dictionary.

    Handles conversion of sets to lists, enums to their name strings,
    and dataclass structures to plain dictionaries.

    Args:
        game_state: The GameState to serialize.

    Returns:
        A JSON-serializable dictionary representing the full game state.
    """
    return {
        "graph": _serialize_graph(game_state.graph),
        "models": {
            model_id: _serialize_model_state(ms)
            for model_id, ms in game_state.models.items()
        },
        "current_turn": game_state.current_turn,
        "max_turns": game_state.max_turns,
        "config": _serialize_game_config(game_state.config),
        "event_log": [_serialize_event(e) for e in game_state.event_log],
    }


def deserialize_game(data: dict) -> GameState:
    """Reconstruct a GameState from a serialized dictionary.

    Args:
        data: A dictionary previously produced by serialize_game.

    Returns:
        A reconstructed GameState.
    """
    graph = _deserialize_graph(data["graph"])
    models = {
        model_id: _deserialize_model_state(ms_data)
        for model_id, ms_data in data["models"].items()
    }
    config = _deserialize_game_config(data["config"])
    event_log = [_deserialize_event(e) for e in data["event_log"]]

    return GameState(
        graph=graph,
        models=models,
        current_turn=data["current_turn"],
        max_turns=data["max_turns"],
        config=config,
        event_log=event_log,
    )


# ---------------------------------------------------------------------------
# Graph serialization helpers
# ---------------------------------------------------------------------------


def _serialize_graph(graph: Graph) -> dict:
    """Serialize a Graph to a dict."""
    return {
        "nodes": {
            node_id: _serialize_node(node)
            for node_id, node in graph.nodes.items()
        },
        "edges": [_serialize_edge(e) for e in graph.edges],
        "start_node": graph.start_node,
        "end_node": graph.end_node,
    }


def _serialize_node(node: Node) -> dict:
    """Serialize a Node to a dict."""
    return {
        "id": node.id,
        "node_type": node.node_type.name,
        "point_value": node.point_value,
    }


def _serialize_edge(edge: Edge) -> dict:
    """Serialize an Edge to a dict."""
    return {
        "source": edge.source,
        "target": edge.target,
        "cost": edge.cost,
        "obstructed": edge.obstructed,
    }


def _deserialize_graph(data: dict) -> Graph:
    """Deserialize a Graph from a dict."""
    nodes: dict[str, Node] = {}
    for node_id, node_data in data["nodes"].items():
        nodes[node_id] = Node(
            id=node_data["id"],
            node_type=NodeType[node_data["node_type"]],
            point_value=node_data["point_value"],
        )

    edges: list[Edge] = []
    for edge_data in data["edges"]:
        edges.append(Edge(
            source=edge_data["source"],
            target=edge_data["target"],
            cost=edge_data["cost"],
            obstructed=edge_data["obstructed"],
        ))

    # Rebuild adjacency from edges
    adjacency: dict[str, list[tuple[str, Edge]]] = {
        node_id: [] for node_id in nodes
    }
    for edge in edges:
        adjacency[edge.source].append((edge.target, edge))
        adjacency[edge.target].append((edge.source, edge))

    return Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node=data["start_node"],
        end_node=data["end_node"],
    )


# ---------------------------------------------------------------------------
# ModelState serialization helpers
# ---------------------------------------------------------------------------


def _serialize_model_state(ms: ModelState) -> dict:
    """Serialize a ModelState to a dict."""
    return {
        "model_id": ms.model_id,
        "strategy_name": ms.strategy_name,
        "current_node": ms.current_node,
        "score": ms.score,
        "has_finished": ms.has_finished,
        "active_checkpoint": ms.active_checkpoint,
        "visited_nodes": sorted(ms.visited_nodes),
        "visible_nodes": sorted(ms.visible_nodes),
        "visible_edges": sorted([list(e) for e in ms.visible_edges]),
        "turns_taken": ms.turns_taken,
        "trap_deaths": ms.trap_deaths,
    }


def _deserialize_model_state(data: dict) -> ModelState:
    """Deserialize a ModelState from a dict."""
    return ModelState(
        model_id=data["model_id"],
        strategy_name=data["strategy_name"],
        current_node=data["current_node"],
        score=data["score"],
        has_finished=data["has_finished"],
        active_checkpoint=data["active_checkpoint"],
        visited_nodes=set(data["visited_nodes"]),
        visible_nodes=set(data["visible_nodes"]),
        visible_edges={tuple(e) for e in data["visible_edges"]},
        turns_taken=data["turns_taken"],
        trap_deaths=data["trap_deaths"],
    )


# ---------------------------------------------------------------------------
# GameConfig serialization helpers
# ---------------------------------------------------------------------------


def _serialize_game_config(config: GameConfig) -> dict:
    """Serialize a GameConfig to a dict."""
    return {
        "graph_config": _serialize_graph_config(config.graph_config),
        "num_models": config.num_models,
        "max_turns": config.max_turns,
        "move_timeout_seconds": config.move_timeout_seconds,
        "completion_bonus_multiplier": config.completion_bonus_multiplier,
        "death_penalty": config.death_penalty,
        "invalid_move_penalty": config.invalid_move_penalty,
        "trap_respawn_penalty": config.trap_respawn_penalty,
    }


def _serialize_graph_config(gc: GraphConfig) -> dict:
    """Serialize a GraphConfig to a dict."""
    return {
        "num_nodes": gc.num_nodes,
        "edge_density": gc.edge_density,
        "trap_probability": gc.trap_probability,
        "clue_probability": gc.clue_probability,
        "map_probability": gc.map_probability,
        "checkpoint_probability": gc.checkpoint_probability,
        "points_probability": gc.points_probability,
        "obstacle_density": gc.obstacle_density,
        "map_reveal_depth": gc.map_reveal_depth,
        "min_point_value": gc.min_point_value,
        "max_point_value": gc.max_point_value,
    }


def _deserialize_game_config(data: dict) -> GameConfig:
    """Deserialize a GameConfig from a dict."""
    gc_data = data["graph_config"]
    graph_config = GraphConfig(
        num_nodes=gc_data["num_nodes"],
        edge_density=gc_data["edge_density"],
        trap_probability=gc_data["trap_probability"],
        clue_probability=gc_data["clue_probability"],
        map_probability=gc_data["map_probability"],
        checkpoint_probability=gc_data["checkpoint_probability"],
        points_probability=gc_data["points_probability"],
        obstacle_density=gc_data["obstacle_density"],
        map_reveal_depth=gc_data["map_reveal_depth"],
        min_point_value=gc_data["min_point_value"],
        max_point_value=gc_data["max_point_value"],
    )

    return GameConfig(
        graph_config=graph_config,
        num_models=data["num_models"],
        max_turns=data["max_turns"],
        move_timeout_seconds=data["move_timeout_seconds"],
        completion_bonus_multiplier=data["completion_bonus_multiplier"],
        death_penalty=data["death_penalty"],
        invalid_move_penalty=data["invalid_move_penalty"],
        trap_respawn_penalty=data["trap_respawn_penalty"],
    )


# ---------------------------------------------------------------------------
# GameEvent serialization helpers
# ---------------------------------------------------------------------------


def _serialize_event(event: GameEvent) -> dict:
    """Serialize a GameEvent to a dict."""
    return {
        "turn": event.turn,
        "model_id": event.model_id,
        "event_type": event.event_type.name,
        "details": event.details,
    }


def _deserialize_event(data: dict) -> GameEvent:
    """Deserialize a GameEvent from a dict."""
    return GameEvent(
        turn=data["turn"],
        model_id=data["model_id"],
        event_type=EventType[data["event_type"]],
        details=data["details"],
    )
