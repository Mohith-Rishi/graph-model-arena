"""Shortest Path strategy — uses Dijkstra on visible graph toward the Ending_Node.

Requirements: 8.3
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


class ShortestPath(ModelStrategy):
    """Computes the shortest known path to the Ending_Node using only visible graph information."""

    @property
    def name(self) -> str:
        return "Shortest_Path"

    def decide_move(self, state: ModelView) -> str:
        neighbors = get_valid_neighbors(state)
        if not neighbors:
            return state.current_node

        end_node = find_end_node(state)
        if end_node is None:
            # End node not yet visible — explore by picking a random neighbor
            return random.choice(neighbors)

        # Compute shortest path to end node
        path = dijkstra(state, end_node)
        if path and path[0] in neighbors:
            return path[0]

        # Path not reachable through visible graph — pick random neighbor
        return random.choice(neighbors)
