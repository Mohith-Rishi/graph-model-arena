"""Game Engine — core orchestrator managing the full game lifecycle.

Responsibilities:
- Accept game configuration and initialize all subsystems
- Coordinate turn execution
- Track game state across turns
- Detect end conditions (all models finished, max turns reached)
- Score remaining models on turn limit by proximity to end node
- Record completion bonuses when models reach the ending node
"""

from __future__ import annotations

import heapq
import logging

from graph_model_arena.graph_generator import generate_graph
from graph_model_arena.model_interface import ModelStrategy
from graph_model_arena.models import (
    EventType,
    GameConfig,
    GameEvent,
    GameState,
    Graph,
    ModelState,
)
from graph_model_arena.score_manager import apply_completion_bonus
from graph_model_arena.turn_manager import execute_turn
from graph_model_arena.visibility_manager import initialize_visibility

logger = logging.getLogger(__name__)


def create_game(
    config: GameConfig,
    strategies: dict[str, ModelStrategy],
) -> GameState:
    """Create and initialize a new game.

    Steps:
    1. Validate configuration
    2. Generate graph from config
    3. Initialize ModelState for each model at start_node with score=0
    4. Initialize visibility (start node + immediate neighbors) per model

    Args:
        config: The game configuration specifying graph params, model count, etc.
        strategies: Mapping of model_id to ModelStrategy instance.

    Returns:
        An initialized GameState ready to be started.

    Raises:
        ValueError: If the configuration is invalid.
    """
    # 1. Validate config
    config.validate()

    # 2. Generate the graph
    graph = generate_graph(config.graph_config)

    # 3. Initialize model states at start_node
    models: dict[str, ModelState] = {}
    for model_id, strategy in strategies.items():
        strategy_name = type(strategy).__name__
        models[model_id] = ModelState(
            model_id=model_id,
            strategy_name=strategy_name,
            current_node=graph.start_node,
            score=0,
        )

    # 4. Build GameState
    game_state = GameState(
        graph=graph,
        models=models,
        current_turn=0,
        max_turns=config.max_turns,
        config=config,
        event_log=[],
    )

    # 5. Initialize visibility for each model
    for model_id in models:
        game_state = initialize_visibility(model_id, graph, game_state)

    return game_state


def start_game(
    game_state: GameState,
    strategies: dict[str, ModelStrategy],
) -> GameState:
    """Run the game loop until an end condition is met.

    End conditions:
    - All models have finished (reached the Ending_Node)
    - Maximum turn limit reached

    On each turn:
    1. Execute the turn (collect moves, validate, resolve)
    2. Check if any model reached end_node — mark as finished, apply bonus
    3. Check end conditions

    On turn limit:
    - Score remaining models by proximity (shortest path distance to end_node)

    Args:
        game_state: An initialized GameState (from create_game).
        strategies: Mapping of model_id to ModelStrategy instance.

    Returns:
        The final GameState after the game has ended.
    """
    end_node = game_state.graph.end_node

    while True:
        # Execute the turn
        game_state = execute_turn(game_state, strategies)

        # Check if any model just reached the end node
        for model_id, model in game_state.models.items():
            if model.has_finished:
                continue
            if model.current_node == end_node:
                # Mark as finished
                model.has_finished = True
                model.turns_taken = game_state.current_turn

                # Apply completion bonus
                game_state.models[model_id] = apply_completion_bonus(
                    model,
                    turns_taken=model.turns_taken,
                    max_turns=game_state.max_turns,
                    multiplier=game_state.config.completion_bonus_multiplier,
                )

                game_state.event_log.append(
                    GameEvent(
                        turn=game_state.current_turn,
                        model_id=model_id,
                        event_type=EventType.GAME_FINISHED,
                        details={
                            "turns_taken": model.turns_taken,
                            "final_score": game_state.models[model_id].score,
                        },
                    )
                )

                logger.info(
                    "Model '%s' reached the end node on turn %d with score %d",
                    model_id,
                    model.turns_taken,
                    game_state.models[model_id].score,
                )

        # Check end condition: all models finished
        if all(m.has_finished for m in game_state.models.values()):
            logger.info("All models have finished. Game over.")
            break

        # Check end condition: max turns reached
        if game_state.current_turn >= game_state.max_turns:
            logger.info(
                "Maximum turn limit (%d) reached. Scoring by proximity.",
                game_state.max_turns,
            )
            _score_remaining_by_proximity(game_state)
            game_state.event_log.append(
                GameEvent(
                    turn=game_state.current_turn,
                    model_id="",
                    event_type=EventType.GAME_ENDED_BY_TURN_LIMIT,
                    details={"max_turns": game_state.max_turns},
                )
            )
            break

    return game_state


def _score_remaining_by_proximity(game_state: GameState) -> None:
    """Score remaining active models by their proximity to the end node.

    Uses Dijkstra's shortest path distance (using edge costs, non-obstructed
    edges only) from each model's current position to the end node.

    Bonus awarded: max(0, max_turns - distance)
    Models already at or very close to the end get a higher proximity bonus.
    """
    end_node = game_state.graph.end_node
    graph = game_state.graph

    for model_id, model in game_state.models.items():
        if model.has_finished:
            continue

        # Mark turns_taken as max_turns for unfinished models
        model.turns_taken = game_state.max_turns

        # Compute shortest path distance from model's position to end_node
        distance = _dijkstra_distance(model.current_node, end_node, graph)

        if distance is not None:
            # Award proximity bonus: max_turns - distance (floored at 0)
            bonus = max(0, game_state.max_turns - distance)
            model.score += bonus
        # If no path exists (shouldn't happen in a valid graph), no bonus

        logger.info(
            "Model '%s' scored proximity bonus. Distance to end: %s, bonus: %d",
            model_id,
            distance if distance is not None else "unreachable",
            bonus if distance is not None else 0,
        )


def _dijkstra_distance(source: str, target: str, graph: "Graph") -> int | None:
    """Compute shortest path distance from source to target using Dijkstra.

    Only considers non-obstructed edges. Returns None if target is unreachable.
    """
    # Priority queue: (distance, node_id)
    pq: list[tuple[int, str]] = [(0, source)]
    dist: dict[str, int] = {source: 0}

    while pq:
        d, node = heapq.heappop(pq)

        if node == target:
            return d

        if d > dist.get(node, float("inf")):
            continue

        for neighbor_id, edge in graph.adjacency.get(node, []):
            if edge.obstructed:
                continue
            new_dist = d + edge.cost
            if new_dist < dist.get(neighbor_id, float("inf")):
                dist[neighbor_id] = new_dist
                heapq.heappush(pq, (new_dist, neighbor_id))

    return None
