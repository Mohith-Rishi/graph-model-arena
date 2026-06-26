"""Balanced Strategist — dynamically switches between explore, collect, and goal-seek.

Requirements: 8.8
"""

from __future__ import annotations

import random

from graph_model_arena.model_interface import ModelStrategy
from graph_model_arena.models import ModelView, NodeType
from graph_model_arena.strategies._helpers import (
    bfs_toward,
    dijkstra,
    find_end_node,
    find_nodes_by_type,
    get_valid_neighbors,
)


class BalancedStrategist(ModelStrategy):
    """Switches between exploration, point collection, and goal-seeking based on turn count and score."""

    def __init__(self) -> None:
        self._visited: set[str] = set()

    @property
    def name(self) -> str:
        return "Balanced_Strategist"

    def decide_move(self, state: ModelView) -> str:
        neighbors = get_valid_neighbors(state)
        if not neighbors:
            return state.current_node

        self._visited.add(state.current_node)

        # Determine phase based on turn number
        # Early game (first 1/3): explore
        # Mid game (1/3 to 2/3): collect points
        # Late game (last 1/3): goal-seek (rush to end)
        # We estimate max_turns from the turn_number heuristically.
        # Since we don't have max_turns in ModelView, use turn thresholds.
        turn = state.turn_number

        if turn < 15:
            return self._explore(state, neighbors)
        elif turn < 40:
            return self._collect(state, neighbors)
        else:
            return self._goal_seek(state, neighbors)

    def _explore(self, state: ModelView, neighbors: list[str]) -> str:
        """Explore: prioritize unvisited nodes and information nodes."""
        # Check for adjacent info nodes
        info_neighbors = [
            n for n in neighbors
            if n in state.visible_nodes
            and state.visible_nodes[n].node_type in (NodeType.CLUE, NodeType.MAP)
            and n not in self._visited
        ]
        if info_neighbors:
            return random.choice(info_neighbors)

        # Prefer unvisited neighbors
        unvisited = [n for n in neighbors if n not in self._visited]
        if unvisited:
            return random.choice(unvisited)
        return random.choice(neighbors)

    def _collect(self, state: ModelView, neighbors: list[str]) -> str:
        """Collect: prioritize Points_Nodes."""
        # Adjacent points nodes not yet visited
        points_neighbors = [
            n for n in neighbors
            if n in state.visible_nodes
            and state.visible_nodes[n].node_type == NodeType.POINTS
            and n not in self._visited
        ]
        if points_neighbors:
            # Pick highest value
            valued = [
                (n, state.visible_nodes[n].point_value) for n in points_neighbors
            ]
            valued.sort(key=lambda x: x[1], reverse=True)
            return valued[0][0]

        # Navigate toward visible points nodes
        all_points = find_nodes_by_type(state, NodeType.POINTS)
        unvisited_points = [p for p in all_points if p not in self._visited]
        if unvisited_points:
            valued = [
                (p, state.visible_nodes[p].point_value) for p in unvisited_points
            ]
            valued.sort(key=lambda x: x[1], reverse=True)
            target = valued[0][0]
            next_step = bfs_toward(state, target)
            if next_step and next_step in neighbors:
                return next_step

        # No points to collect — explore
        return self._explore(state, neighbors)

    def _goal_seek(self, state: ModelView, neighbors: list[str]) -> str:
        """Goal-seek: rush toward the Ending_Node."""
        end_node = find_end_node(state)
        if end_node is not None:
            path = dijkstra(state, end_node)
            if path and path[0] in neighbors:
                return path[0]

        # End not visible — explore to find it
        unvisited = [n for n in neighbors if n not in self._visited]
        if unvisited:
            return random.choice(unvisited)
        return random.choice(neighbors)
