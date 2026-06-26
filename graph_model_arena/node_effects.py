"""Node Effect Processor — processes node effects when a model enters a node."""

from __future__ import annotations

import random

from graph_model_arena.models import (
    EventType,
    GameEvent,
    GameState,
    ModelState,
    Node,
    NodeType,
)
from graph_model_arena.score_manager import (
    apply_death_penalty,
    apply_points,
    apply_trap_respawn_penalty,
)
from graph_model_arena.visibility_manager import expand_visibility


def process_node_effect(
    model_state: ModelState, node: Node, game_state: GameState
) -> ModelState:
    """Process all effects of a node on a model that enters it.

    Effects are processed in order:
    1. Checkpoint activation
    2. Trap check (respawn logic)
    3. Clue reveal
    4. Map reveal
    5. Points collection
    """
    model_state = _process_checkpoint(model_state, node, game_state)
    model_state = _process_trap(model_state, node, game_state)
    model_state = _process_clue(model_state, node, game_state)
    model_state = _process_map(model_state, node, game_state)
    model_state = _process_points(model_state, node, game_state)
    return model_state


def _process_checkpoint(
    model_state: ModelState, node: Node, game_state: GameState
) -> ModelState:
    """If node is a checkpoint, set it as the model's active respawn point."""
    if node.node_type != NodeType.CHECKPOINT:
        return model_state

    model_state.active_checkpoint = node.id

    game_state.event_log.append(
        GameEvent(
            turn=game_state.current_turn,
            model_id=model_state.model_id,
            event_type=EventType.CHECKPOINT_ACTIVATED,
            details={"checkpoint_node": node.id},
        )
    )
    return model_state


def _process_trap(
    model_state: ModelState, node: Node, game_state: GameState
) -> ModelState:
    """If node is a trap, respawn model at checkpoint or start with penalty."""
    if node.node_type != NodeType.TRAP:
        return model_state

    model_state.trap_deaths += 1

    if model_state.active_checkpoint is not None:
        # Respawn at checkpoint with trap_respawn_penalty
        model_state = apply_trap_respawn_penalty(
            model_state, game_state.config.trap_respawn_penalty
        )
        model_state.current_node = model_state.active_checkpoint

        game_state.event_log.append(
            GameEvent(
                turn=game_state.current_turn,
                model_id=model_state.model_id,
                event_type=EventType.TRAP_RESPAWN_CHECKPOINT,
                details={
                    "trap_node": node.id,
                    "respawn_node": model_state.active_checkpoint,
                    "penalty": game_state.config.trap_respawn_penalty,
                },
            )
        )
    else:
        # Respawn at Starting_Node with death_penalty
        model_state = apply_death_penalty(
            model_state, game_state.config.death_penalty
        )
        model_state.current_node = game_state.graph.start_node

        game_state.event_log.append(
            GameEvent(
                turn=game_state.current_turn,
                model_id=model_state.model_id,
                event_type=EventType.TRAP_RESPAWN_START,
                details={
                    "trap_node": node.id,
                    "respawn_node": game_state.graph.start_node,
                    "penalty": game_state.config.death_penalty,
                },
            )
        )

    return model_state


def _process_clue(
    model_state: ModelState, node: Node, game_state: GameState
) -> ModelState:
    """If node is a clue, reveal one random neighbor's type to the model."""
    if node.node_type != NodeType.CLUE:
        return model_state

    graph = game_state.graph
    neighbors = graph.adjacency.get(node.id, [])

    if not neighbors:
        return model_state

    # Pick one random neighbor to reveal
    neighbor_id, _ = random.choice(neighbors)
    neighbor_node = graph.nodes.get(neighbor_id)

    if neighbor_node is None:
        return model_state

    # Reveal by adding the neighbor to visible nodes
    model_state.visible_nodes.add(neighbor_id)

    game_state.event_log.append(
        GameEvent(
            turn=game_state.current_turn,
            model_id=model_state.model_id,
            event_type=EventType.CLUE_RECEIVED,
            details={
                "clue_node": node.id,
                "revealed_node": neighbor_id,
                "revealed_type": neighbor_node.node_type.name,
            },
        )
    )

    return model_state


def _process_map(
    model_state: ModelState, node: Node, game_state: GameState
) -> ModelState:
    """If node is a map, expand model's visibility by configured depth."""
    if node.node_type != NodeType.MAP:
        return model_state

    depth = game_state.config.graph_config.map_reveal_depth

    # Use visibility manager to expand visibility from this node
    expand_visibility(model_state.model_id, node.id, depth, game_state)

    game_state.event_log.append(
        GameEvent(
            turn=game_state.current_turn,
            model_id=model_state.model_id,
            event_type=EventType.MAP_REVEALED,
            details={
                "map_node": node.id,
                "depth": depth,
            },
        )
    )

    return model_state


def _process_points(
    model_state: ModelState, node: Node, game_state: GameState
) -> ModelState:
    """If node is a points node, add points on first visit only."""
    if node.node_type != NodeType.POINTS:
        return model_state

    # apply_points checks first visit internally
    old_score = model_state.score
    model_state = apply_points(model_state, node)

    points_awarded = model_state.score - old_score
    if points_awarded > 0:
        game_state.event_log.append(
            GameEvent(
                turn=game_state.current_turn,
                model_id=model_state.model_id,
                event_type=EventType.POINTS_COLLECTED,
                details={
                    "points_node": node.id,
                    "points_awarded": points_awarded,
                },
            )
        )

    return model_state
