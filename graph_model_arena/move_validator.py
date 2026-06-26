"""Move Validator — validates model move submissions."""

from __future__ import annotations

from graph_model_arena.models import GameState, MoveResult


def validate_move(
    model_id: str, target_node: str, game_state: GameState
) -> MoveResult:
    """Validate that a model's move to target_node is legal.

    A move is valid if and only if:
    1. The target node is adjacent to the model's current position.
    2. The connecting edge is not obstructed by an obstacle.

    Returns a MoveResult indicating valid/invalid with a reason string.
    """
    model_state = game_state.models.get(model_id)
    if model_state is None:
        return MoveResult(valid=False, reason=f"Model '{model_id}' not found in game state")

    current_node = model_state.current_node
    graph = game_state.graph

    # Get adjacency list for the model's current position
    neighbors = graph.adjacency.get(current_node, [])

    # Check if target_node is adjacent
    for neighbor_id, edge in neighbors:
        if neighbor_id == target_node:
            # Found the edge — check if it's obstructed
            if edge.obstructed:
                return MoveResult(
                    valid=False,
                    reason=f"Edge from '{current_node}' to '{target_node}' is obstructed",
                )
            return MoveResult(valid=True)

    # Target node is not adjacent
    return MoveResult(
        valid=False,
        reason=f"Node '{target_node}' is not adjacent to current position '{current_node}'",
    )
