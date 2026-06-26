"""Cautious Navigator strategy — avoids unknown nodes, prioritizes Checkpoint_Nodes.

Requirements: 8.4
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


class CautiousNavigator(ModelStrategy):
    """Avoids unknown nodes when possible and prioritizes Checkpoint_Nodes."""

    @property
    def name(self) -> str:
        return "Cautious_Navigator"

    def decide_move(self, state: ModelView) -> str:
        neighbors = get_valid_neighbors(state)
        if not neighbors:
            return state.current_node

        # Classify neighbors by knowledge
        known_neighbors = [n for n in neighbors if n in state.visible_nodes]
        unknown_neighbors = [n for n in neighbors if n not in state.visible_nodes]

        # Prefer known neighbors to avoid the unknown
        safe_pool = known_neighbors if known_neighbors else neighbors

        # Among safe neighbors, avoid TRAP nodes
        non_trap = [
            n for n in safe_pool
            if n in state.visible_nodes
            and state.visible_nodes[n].node_type != NodeType.TRAP
        ]
        if non_trap:
            safe_pool = non_trap

        # Prioritize checkpoint nodes among safe neighbors
        checkpoint_neighbors = [
            n for n in safe_pool
            if n in state.visible_nodes
            and state.visible_nodes[n].node_type == NodeType.CHECKPOINT
        ]
        if checkpoint_neighbors:
            return random.choice(checkpoint_neighbors)

        # If no checkpoint neighbor, try to navigate toward a visible checkpoint
        if not state.has_checkpoint:
            checkpoints = find_nodes_by_type(state, NodeType.CHECKPOINT)
            if checkpoints:
                # Move toward the nearest checkpoint
                for cp in checkpoints:
                    next_step = bfs_toward(state, cp)
                    if next_step and next_step in safe_pool:
                        return next_step

        # Fallback: pick from safe pool
        return random.choice(safe_pool)
