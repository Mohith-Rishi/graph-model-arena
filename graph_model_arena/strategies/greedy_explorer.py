"""Greedy Explorer strategy — prioritizes unvisited nodes and highest-value Points_Nodes.

Requirements: 8.2
"""

from __future__ import annotations

import random

from graph_model_arena.model_interface import ModelStrategy
from graph_model_arena.models import ModelView, NodeType
from graph_model_arena.strategies._helpers import (
    bfs_toward,
    find_nodes_by_type,
    get_valid_neighbors,
)


class GreedyExplorer(ModelStrategy):
    """Prioritizes unvisited nodes and moves toward the highest-value visible Points_Node."""

    def __init__(self) -> None:
        self._visited: set[str] = set()

    @property
    def name(self) -> str:
        return "Greedy_Explorer"

    def decide_move(self, state: ModelView) -> str:
        neighbors = get_valid_neighbors(state)
        if not neighbors:
            return state.current_node

        self._visited.add(state.current_node)

        # Prioritize unvisited neighbors
        unvisited_neighbors = [n for n in neighbors if n not in self._visited]
        if unvisited_neighbors:
            # Among unvisited neighbors, prefer Points_Nodes with highest value
            points_neighbors = []
            for n in unvisited_neighbors:
                node = state.visible_nodes.get(n)
                if node and node.node_type == NodeType.POINTS:
                    points_neighbors.append((n, node.point_value))
            if points_neighbors:
                points_neighbors.sort(key=lambda x: x[1], reverse=True)
                return points_neighbors[0][0]
            return random.choice(unvisited_neighbors)

        # No unvisited neighbors — move toward the highest-value visible Points_Node
        points_nodes = find_nodes_by_type(state, NodeType.POINTS)
        # Filter to unvisited points nodes
        unvisited_points = [
            (nid, state.visible_nodes[nid].point_value)
            for nid in points_nodes
            if nid not in self._visited
        ]
        if unvisited_points:
            unvisited_points.sort(key=lambda x: x[1], reverse=True)
            target = unvisited_points[0][0]
            next_step = bfs_toward(state, target)
            if next_step and next_step in neighbors:
                return next_step

        # Fallback: pick a random neighbor
        return random.choice(neighbors)
