"""Random Walker strategy — picks a random adjacent node each turn.

Requirements: 8.1
"""

from __future__ import annotations

import random

from graph_model_arena.model_interface import ModelStrategy
from graph_model_arena.models import ModelView
from graph_model_arena.strategies._helpers import get_valid_neighbors


class RandomWalker(ModelStrategy):
    """Selects a random adjacent node each turn."""

    @property
    def name(self) -> str:
        return "Random_Walker"

    def decide_move(self, state: ModelView) -> str:
        neighbors = get_valid_neighbors(state)
        if not neighbors:
            return state.current_node
        return random.choice(neighbors)
