"""Risk Taker strategy — explores aggressively, ignores trap risk, seeks Points_Nodes.

Requirements: 8.5
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


class RiskTaker(ModelStrategy):
    """Explores aggressively, ignoring potential traps in favor of discovering Points_Nodes."""

    def __init__(self) -> None:
        self._visited: set[str] = set()

    @property
    def name(self) -> str:
        return "Risk_Taker"

    def decide_move(self, state: ModelView) -> str:
        neighbors = get_valid_neighbors(state)
        if not neighbors:
            return state.current_node

        self._visited.add(state.current_node)

        # Always prefer unvisited neighbors (aggressive exploration)
        unvisited = [n for n in neighbors if n not in self._visited]

        # Among options, prioritize Points_Nodes
        pool = unvisited if unvisited else neighbors

        points_in_pool = [
            (n, state.visible_nodes[n].point_value)
            for n in pool
            if n in state.visible_nodes
            and state.visible_nodes[n].node_type == NodeType.POINTS
            and n not in self._visited
        ]
        if points_in_pool:
            points_in_pool.sort(key=lambda x: x[1], reverse=True)
            return points_in_pool[0][0]

        # Try to navigate toward a visible Points_Node (even far away)
        all_points = find_nodes_by_type(state, NodeType.POINTS)
        unvisited_points = [p for p in all_points if p not in self._visited]
        if unvisited_points:
            # Pick the highest-value unvisited points node
            valued = [
                (p, state.visible_nodes[p].point_value) for p in unvisited_points
            ]
            valued.sort(key=lambda x: x[1], reverse=True)
            target = valued[0][0]
            next_step = bfs_toward(state, target)
            if next_step and next_step in neighbors:
                return next_step

        # Fallback: explore aggressively — prefer unvisited, else random
        if unvisited:
            return random.choice(unvisited)
        return random.choice(neighbors)
