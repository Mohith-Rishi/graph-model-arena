"""Score Manager — manages scoring logic for Graph Model Arena."""

from __future__ import annotations

from graph_model_arena.models import (
    ModelState,
    Node,
    NodeType,
    RankedModel,
    TerminationCause,
)


def apply_points(model_state: ModelState, node: Node) -> ModelState:
    """Add point_value to score on first visit only. Zero if revisited."""
    if node.node_type != NodeType.POINTS:
        return model_state
    if node.id not in model_state.visited_nodes:
        model_state.score += node.point_value
    return model_state


def apply_completion_bonus(
    model_state: ModelState,
    turns_taken: int,
    max_turns: int,
    multiplier: float,
) -> ModelState:
    """Award completion bonus: (max_turns - turns_taken) * multiplier."""
    bonus = int((max_turns - turns_taken) * multiplier)
    model_state.score += bonus
    return model_state


def apply_death_penalty(model_state: ModelState, penalty: int) -> ModelState:
    """Deduct death penalty for trap respawn at start (no checkpoint)."""
    model_state.score -= penalty
    return model_state


def apply_trap_respawn_penalty(model_state: ModelState, penalty: int) -> ModelState:
    """Deduct penalty for trap respawn at checkpoint."""
    model_state.score -= penalty
    return model_state


def apply_invalid_move_penalty(model_state: ModelState, penalty: int) -> ModelState:
    """Deduct penalty for an invalid move."""
    model_state.score -= penalty
    return model_state


def compute_final_rankings(model_states: list[ModelState]) -> list[RankedModel]:
    """Rank models by score descending, ties broken by fewer turns taken (ascending)."""
    # Sort: highest score first, then fewest turns for ties
    sorted_models = sorted(
        model_states,
        key=lambda m: (-m.score, m.turns_taken),
    )

    rankings: list[RankedModel] = []
    for i, model in enumerate(sorted_models, start=1):
        cause = (
            TerminationCause.FINISHED
            if model.has_finished
            else TerminationCause.TURN_LIMIT
        )
        rankings.append(
            RankedModel(
                rank=i,
                model_id=model.model_id,
                strategy_name=model.strategy_name,
                final_score=model.score,
                turns_taken=model.turns_taken,
                nodes_visited=len(model.visited_nodes),
                cause_of_termination=cause,
                path=list(model.visited_nodes),
            )
        )

    return rankings
