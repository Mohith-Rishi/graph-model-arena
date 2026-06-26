"""Shared helper utilities for model strategies."""

from __future__ import annotations

import heapq
from collections import deque

from graph_model_arena.models import ModelView, NodeType


def get_valid_neighbors(state: ModelView) -> list[str]:
    """Get all valid (non-obstructed) adjacent node IDs from the current node.

    Filters visible_edges for edges connected to current_node that are not obstructed,
    and returns the neighbor node IDs.
    """
    current = state.current_node
    neighbors: list[str] = []
    for source, target, cost, obstructed in state.visible_edges:
        if obstructed:
            continue
        if source == current:
            neighbors.append(target)
        elif target == current:
            neighbors.append(source)
    return neighbors


def dijkstra(
    state: ModelView, target_node: str
) -> list[str] | None:
    """Compute shortest path from current_node to target_node using visible edges.

    Returns the path as a list of node IDs (excluding current_node), or None if
    no path is found.
    """
    current = state.current_node
    if current == target_node:
        return []

    # Build adjacency from visible non-obstructed edges
    adj: dict[str, list[tuple[str, int]]] = {}
    for source, target, cost, obstructed in state.visible_edges:
        if obstructed:
            continue
        adj.setdefault(source, []).append((target, cost))
        adj.setdefault(target, []).append((source, cost))

    # Standard Dijkstra
    dist: dict[str, float] = {current: 0}
    prev: dict[str, str | None] = {current: None}
    heap: list[tuple[float, str]] = [(0, current)]

    while heap:
        d, node = heapq.heappop(heap)
        if node == target_node:
            # Reconstruct path
            path: list[str] = []
            n: str | None = target_node
            while n is not None and n != current:
                path.append(n)
                n = prev.get(n)
            path.reverse()
            return path
        if d > dist.get(node, float("inf")):
            continue
        for neighbor, cost in adj.get(node, []):
            new_dist = d + cost
            if new_dist < dist.get(neighbor, float("inf")):
                dist[neighbor] = new_dist
                prev[neighbor] = node
                heapq.heappush(heap, (new_dist, neighbor))

    return None  # No path found


def bfs_toward(
    state: ModelView, target_node: str
) -> str | None:
    """BFS from current_node toward target_node. Returns the first step or None."""
    path = dijkstra(state, target_node)
    if path:
        return path[0]
    return None


def find_nodes_by_type(state: ModelView, node_type: NodeType) -> list[str]:
    """Find all visible nodes of a specific type."""
    return [
        node_id
        for node_id, node in state.visible_nodes.items()
        if node.node_type == node_type
    ]


def find_end_node(state: ModelView) -> str | None:
    """Find the Ending_Node in visible nodes."""
    ends = find_nodes_by_type(state, NodeType.END)
    return ends[0] if ends else None
