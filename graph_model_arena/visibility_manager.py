"""Visibility Manager — manages per-model fog-of-war state."""

from __future__ import annotations

from collections import deque

from graph_model_arena.models import Edge, GameState, Graph, Node, VisibleGraph


def initialize_visibility(model_id: str, graph: Graph, game_state: GameState) -> GameState:
    """Set a model's visibility to the start node and its immediate neighbors."""
    model = game_state.models[model_id]
    start = graph.start_node

    # Add start node itself
    model.visible_nodes.add(start)

    # Add all neighbors of the start node
    for neighbor_id, edge in graph.adjacency.get(start, []):
        model.visible_nodes.add(neighbor_id)
        # Store edges as sorted tuple pair for consistency
        model.visible_edges.add(_edge_key(edge.source, edge.target))

    return game_state


def expand_visibility(
    model_id: str, center_node: str, depth: int, game_state: GameState
) -> GameState:
    """Expand a model's visibility via BFS from center_node up to given depth."""
    model = game_state.models[model_id]
    graph = game_state.graph

    # BFS expansion
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque()
    queue.append((center_node, 0))
    visited.add(center_node)

    while queue:
        node_id, dist = queue.popleft()
        model.visible_nodes.add(node_id)

        if dist < depth:
            for neighbor_id, edge in graph.adjacency.get(node_id, []):
                model.visible_edges.add(_edge_key(edge.source, edge.target))
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, dist + 1))

    return game_state


def get_visible_graph(model_id: str, game_state: GameState) -> VisibleGraph:
    """Return a filtered graph view containing only what the model can see."""
    model = game_state.models[model_id]
    graph = game_state.graph

    # Collect visible nodes
    visible_nodes: dict[str, Node] = {}
    for node_id in model.visible_nodes:
        if node_id in graph.nodes:
            visible_nodes[node_id] = graph.nodes[node_id]

    # Collect visible edges (both endpoints must be visible)
    visible_edges: list[Edge] = []
    for edge in graph.edges:
        key = _edge_key(edge.source, edge.target)
        if key in model.visible_edges:
            visible_edges.append(edge)

    # Build adjacency for visible portion
    adjacency: dict[str, list[tuple[str, Edge]]] = {}
    for edge in visible_edges:
        if edge.source in visible_nodes and edge.target in visible_nodes:
            adjacency.setdefault(edge.source, []).append((edge.target, edge))
            adjacency.setdefault(edge.target, []).append((edge.source, edge))

    return VisibleGraph(nodes=visible_nodes, edges=visible_edges, adjacency=adjacency)


def _edge_key(source: str, target: str) -> tuple[str, str]:
    """Create a canonical edge key (sorted tuple) for consistent lookups."""
    return (min(source, target), max(source, target))
