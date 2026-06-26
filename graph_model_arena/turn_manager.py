"""Turn Manager — handles the execution of a single turn."""

from __future__ import annotations

import concurrent.futures
import logging

from graph_model_arena.model_interface import ModelStrategy
from graph_model_arena.models import (
    EventType,
    GameEvent,
    GameState,
    ModelView,
    ValidatedMove,
)
from graph_model_arena.move_validator import validate_move
from graph_model_arena.score_manager import apply_invalid_move_penalty
from graph_model_arena.state_resolver import resolve_moves
from graph_model_arena.visibility_manager import get_visible_graph

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helper: build ModelView for a model
# ---------------------------------------------------------------------------


def _build_model_view(model_id: str, game_state: GameState) -> ModelView:
    """Construct a ModelView for the given model from the current game state."""
    model = game_state.models[model_id]
    visible_graph = get_visible_graph(model_id, game_state)

    # Build visible_edges as list of (source, target, cost, obstructed)
    visible_edges: list[tuple[str, str, int, bool]] = [
        (edge.source, edge.target, edge.cost, edge.obstructed)
        for edge in visible_graph.edges
    ]

    return ModelView(
        current_node=model.current_node,
        visible_nodes=visible_graph.nodes,
        visible_edges=visible_edges,
        current_score=model.score,
        turn_number=game_state.current_turn,
        has_checkpoint=model.active_checkpoint is not None,
        checkpoint_node=model.active_checkpoint,
    )


# ---------------------------------------------------------------------------
# Core turn execution
# ---------------------------------------------------------------------------


def execute_turn(
    game_state: GameState,
    strategies: dict[str, ModelStrategy],
) -> GameState:
    """Execute a single game turn.

    Steps:
    1. Collect move decisions from all active (non-finished) models with timeout.
    2. Validate each move via Move Validator.
    3. Apply invalid move penalty for bad moves.
    4. Handle timeout as no-op with no penalty.
    5. Handle model exceptions as no-op with no penalty (log error).
    6. Pass validated moves to State Resolver.
    7. Increment turn counter.

    Args:
        game_state: The current game state.
        strategies: Mapping of model_id to ModelStrategy instance.

    Returns:
        Updated GameState after the turn is resolved.
    """
    timeout = game_state.config.move_timeout_seconds
    active_models = [
        model_id
        for model_id, model in game_state.models.items()
        if not model.has_finished
    ]

    # Collect moves from all active models
    raw_moves: dict[str, str | None] = {}

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=len(active_models) or 1
    ) as executor:
        future_to_model: dict[concurrent.futures.Future[str], str] = {}

        for model_id in active_models:
            model_view = _build_model_view(model_id, game_state)
            strategy = strategies.get(model_id)

            if strategy is None:
                # No strategy registered — treat as no-op
                logger.warning(
                    "No strategy registered for model '%s', treating as no-op",
                    model_id,
                )
                raw_moves[model_id] = None
                continue

            future = executor.submit(_call_strategy, strategy, model_view)
            future_to_model[future] = model_id

        # Collect results with timeout
        for future, model_id in future_to_model.items():
            try:
                result = future.result(timeout=timeout)
                raw_moves[model_id] = result
            except concurrent.futures.TimeoutError:
                # Timeout: no-op, no penalty
                raw_moves[model_id] = None
                game_state.event_log.append(
                    GameEvent(
                        turn=game_state.current_turn,
                        model_id=model_id,
                        event_type=EventType.TIMEOUT,
                        details={"timeout_seconds": timeout},
                    )
                )
                logger.info(
                    "Model '%s' timed out on turn %d",
                    model_id,
                    game_state.current_turn,
                )
                # Cancel the future to clean up
                future.cancel()
            except Exception as exc:
                # Model exception: no-op, no penalty, log error
                raw_moves[model_id] = None
                logger.error(
                    "Model '%s' raised exception on turn %d: %s",
                    model_id,
                    game_state.current_turn,
                    exc,
                )

    # Validate moves and build ValidatedMove list
    validated_moves: list[ValidatedMove] = []

    for model_id in active_models:
        target = raw_moves.get(model_id)

        if target is None:
            # No-op (timeout or exception) — model stays in place, no penalty
            continue

        # Validate the move
        move_result = validate_move(model_id, target, game_state)

        if move_result.valid:
            validated_moves.append(
                ValidatedMove(
                    model_id=model_id,
                    target_node=target,
                    valid=True,
                )
            )
        else:
            # Invalid move: keep model at current position, apply penalty
            model = game_state.models[model_id]
            game_state.models[model_id] = apply_invalid_move_penalty(
                model, game_state.config.invalid_move_penalty
            )
            game_state.event_log.append(
                GameEvent(
                    turn=game_state.current_turn,
                    model_id=model_id,
                    event_type=EventType.INVALID_MOVE,
                    details={
                        "target_node": target,
                        "reason": move_result.reason,
                    },
                )
            )
            logger.info(
                "Model '%s' submitted invalid move '%s' on turn %d: %s",
                model_id,
                target,
                game_state.current_turn,
                move_result.reason,
            )

    # Resolve all valid moves
    game_state = resolve_moves(validated_moves, game_state)

    # Increment turn counter
    game_state.current_turn += 1

    return game_state


def _call_strategy(strategy: ModelStrategy, model_view: ModelView) -> str:
    """Call the strategy's decide_move method.

    This is extracted to run in a thread for timeout support.
    Exceptions propagate to the caller for handling.
    """
    return strategy.decide_move(model_view)
