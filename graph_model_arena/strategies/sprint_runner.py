"""Sprint Runner strategy — beelines to the Ending_Node, ignoring points.

Requirements: 8.7
"""

from __future__ import annotations

import random

from graph_model_arena.model_interface import ModelStrategy
from graph_model_arena.models import ModelView
from graph_model_arena.strategies._helpers import (
    dijkstra,
    find_end_node,
    get_valid_neighbors,
)


class SprintRunner(ModelStrategy):
    """Moves toward the Ending_Node as fast as possible, ignoring points collection."""

    def __init__(self) -> None:
        self._visited: set[str] = set()

    @property
    def name(self) -> str:
        return "Sprint_Runner"

    def decide_move(self, state: ModelView) -> str:
        neighbors = get_valid_neighbors(state)
        if not neighbors:
            return state.current_node

        self._visited.add(state.current_node)

        end_node = find_end_node(state)
        if end_node is not None:
            # Use Dijkstra to find shortest path to end
            path = dijkstra(state, end_node)
            if path and path[0] in neighbors:
                return path[0]

        # End node not yet visible — explore to find it
        # Prefer unvisited neighbors to discover the end faster
        unvisited = [n for n in neighbors if n not in self._visited]
        if unvisited:
            return random.choice(unvisited)
        return random.choice(neighbors)
