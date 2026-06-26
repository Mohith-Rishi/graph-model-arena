"""State Resolver — resolves validated moves and updates game state."""

from __future__ import annotations

from graph_model_arena.models import (
    EventType,
    GameEvent,
    GameState,
    ValidatedMove,
)
from graph_model_arena.node_effects import process_node_effect
from graph_model_arena.visibility_manager import expand_visibility


def resolve_moves(moves: list[ValidatedMove], game_state: GameState) -> GameState:
    """Resolve all validated moves simultaneously and update game state.

    Steps for each valid move:
    1. Move the model to the target node (update position)
    2. Add target node to visited_nodes
    3. Process node effects (checkpoint, trap, clue, map, points)
    4. Expand visibility from the model's final position (depth 1)

    All models are moved first, then effects are processed. This ensures
    simultaneous resolution — one model's move doesn't affect another's
    validation within the same turn.
    """
    graph = game_state.graph

    # Phase 1: Move all models to their target nodes simultaneously
    for move in moves:
        if not move.valid:
            continue

        model = game_state.models[move.model_id]
        model.current_node = move.target_node

        # Log the move event
        game_state.event_log.append(
            GameEvent(
                turn=game_state.current_turn,
                model_id=move.model_id,
                event_type=EventType.MOVE,
                details={
                    "target_node": move.target_node,
                },
            )
        )

    # Phase 2: Process node effects for each moved model
    for move in moves:
        if not move.valid:
            continue

        model = game_state.models[move.model_id]
        node = graph.nodes[move.target_node]

        # Process node effects (may change position due to trap respawn)
        # Note: we process effects BEFORE adding to visited_nodes so that
        # points nodes correctly detect first visit
        updated_model = process_node_effect(model, node, game_state)
        game_state.models[move.model_id] = updated_model

        # Add to visited_nodes after effects are processed
        updated_model.visited_nodes.add(move.target_node)

    # Phase 3: Expand visibility from each model's final position (depth 1)
    for move in moves:
        if not move.valid:
            continue

        model = game_state.models[move.model_id]
        # Expand from the model's current position (which may have changed
        # due to trap respawn — could be checkpoint or Starting_Node)
        expand_visibility(model.model_id, model.current_node, 1, game_state)

    return game_state
