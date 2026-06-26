"""Clue Seeker strategy — prioritizes Clue_Nodes and Map_Nodes first.

Requirements: 8.6
"""

from __future__ import annotations

import random

from graph_model_arena.model_interface import ModelStrategy
from graph_model_arena.models import ModelView, NodeType
from graph_model_arena.strategies._helpers import (
    bfs_toward,
    find_end_node,
    find_nodes_by_type,
    get_valid_neighbors,
)


class ClueSeeker(ModelStrategy):
    """Prioritizes visiting Clue_Nodes and Map_Nodes to maximize information before navigating to the Ending_Node."""

    def __init__(self) -> None:
        self._visited: set[str] = set()

    @property
    def name(self) -> str:
        return "Clue_Seeker"

    def decide_move(self, state: ModelView) -> str:
        neighbors = get_valid_neighbors(state)
        if not neighbors:
            return state.current_node

        self._visited.add(state.current_node)

        # Check for adjacent Clue or Map nodes (not yet visited)
        info_neighbors = [
            n for n in neighbors
            if n in state.visible_nodes
            and state.visible_nodes[n].node_type in (NodeType.CLUE, NodeType.MAP)
            and n not in self._visited
        ]
        if info_neighbors:
            # Prefer Map nodes over Clue nodes (more info)
            map_neighbors = [
                n for n in info_neighbors
                if state.visible_nodes[n].node_type == NodeType.MAP
            ]
            if map_neighbors:
                return random.choice(map_neighbors)
            return random.choice(info_neighbors)

        # Navigate toward visible Clue/Map nodes not yet visited
        clue_nodes = find_nodes_by_type(state, NodeType.CLUE)
        map_nodes = find_nodes_by_type(state, NodeType.MAP)
        info_targets = [
            n for n in clue_nodes + map_nodes if n not in self._visited
        ]
        if info_targets:
            for target in info_targets:
                next_step = bfs_toward(state, target)
                if next_step and next_step in neighbors:
                    return next_step

        # No more info nodes to seek — head toward the end
        end_node = find_end_node(state)
        if end_node:
            next_step = bfs_toward(state, end_node)
            if next_step and next_step in neighbors:
                return next_step

        # Fallback: explore unvisited neighbors
        unvisited = [n for n in neighbors if n not in self._visited]
        if unvisited:
            return random.choice(unvisited)
        return random.choice(neighbors)
