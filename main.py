"""Graph Model Arena — CLI entry point.

Run a competitive AI game on a dynamically generated graph.

Usage:
    python main.py [OPTIONS]

Options:
    --num-nodes      Number of graph nodes (20-200, default: 30)
    --num-models     Number of competing models (2-8, default: 4)
    --max-turns      Maximum turns before game ends (default: 50)
    --edge-density   Edge density beyond spanning tree (0.0-1.0, default: 0.3)
    --output         Output JSON file path (default: game_result.json)
    --seed           Random seed for reproducibility (optional)
"""

from __future__ import annotations

import argparse
import json
import logging
import random
import sys

from graph_model_arena.game_engine import create_game, start_game
from graph_model_arena.game_reporter import generate_summary, serialize_game
from graph_model_arena.model_interface import ModelRegistry
from graph_model_arena.models import GameConfig, GraphConfig
from graph_model_arena.result_store import GameResult, JsonFileResultStore
from graph_model_arena.strategies import (
    BalancedStrategist,
    CautiousNavigator,
    ClueSeeker,
    GreedyExplorer,
    RandomWalker,
    RiskTaker,
    ShortestPath,
    SprintRunner,
)

ALL_STRATEGIES = [
    RandomWalker,
    GreedyExplorer,
    ShortestPath,
    CautiousNavigator,
    RiskTaker,
    ClueSeeker,
    SprintRunner,
    BalancedStrategist,
]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse command-line arguments with sensible defaults."""
    parser = argparse.ArgumentParser(
        description="Graph Model Arena — competitive AI graph navigation game"
    )
    parser.add_argument(
        "--num-nodes", type=int, default=30,
        help="Number of graph nodes (20-200, default: 30)"
    )
    parser.add_argument(
        "--num-models", type=int, default=4,
        help="Number of competing models (2-8, default: 4)"
    )
    parser.add_argument(
        "--max-turns", type=int, default=50,
        help="Maximum turns before game ends (default: 50)"
    )
    parser.add_argument(
        "--edge-density", type=float, default=0.3,
        help="Edge density (0.0-1.0, default: 0.3)"
    )
    parser.add_argument(
        "--results-file", type=str, default="game_results.json",
        help="Results log file path (default: game_results.json)"
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducibility (optional)"
    )
    return parser.parse_args(argv)


def build_config(args: argparse.Namespace) -> GameConfig:
    """Build a GameConfig from parsed CLI arguments."""
    graph_config = GraphConfig(
        num_nodes=args.num_nodes,
        edge_density=args.edge_density,
    )
    return GameConfig(
        graph_config=graph_config,
        num_models=args.num_models,
        max_turns=args.max_turns,
    )


def register_models(registry: ModelRegistry, num_models: int) -> None:
    """Register model strategies up to the requested count.

    Selects from the pool of 8 built-in strategies. If num_models <= 8,
    picks the first num_models strategies. Strategy instances get descriptive IDs.
    """
    strategies_to_use = ALL_STRATEGIES[:num_models]
    for strategy_cls in strategies_to_use:
        instance = strategy_cls()
        registry.register(instance, model_id=instance.name)


def print_summary(summary) -> None:
    """Print a human-readable game summary to stdout."""
    print("\n" + "=" * 60)
    print("  GRAPH MODEL ARENA — GAME RESULTS")
    print("=" * 60)

    print(f"\n  Total turns played: {summary.total_turns}")
    print(f"  Graph: {summary.graph_stats.get('num_nodes', '?')} nodes, "
          f"{summary.graph_stats.get('num_edges', '?')} edges")
    print()

    print("  FINAL RANKINGS")
    print("  " + "-" * 56)
    print(f"  {'Rank':<6}{'Model':<24}{'Score':<8}{'Turns':<8}{'Status'}")
    print("  " + "-" * 56)

    for rm in summary.rankings:
        status = rm.cause_of_termination.name.lower().replace("_", " ")
        print(f"  {rm.rank:<6}{rm.strategy_name:<24}{rm.final_score:<8}"
              f"{rm.turns_taken:<8}{status}")

    print("  " + "-" * 56)
    print()


def main(argv: list[str] | None = None) -> None:
    """Main entry point: configure, run, report, and serialize."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s | %(name)s | %(message)s",
    )

    args = parse_args(argv)

    # Set random seed if provided
    if args.seed is not None:
        random.seed(args.seed)

    # Build configuration
    config = build_config(args)

    # Register model strategies
    registry = ModelRegistry()
    register_models(registry, config.num_models)
    strategies = registry.get_all()

    print(f"Starting game with {len(strategies)} models on a "
          f"{config.graph_config.num_nodes}-node graph (max {config.max_turns} turns)...")

    # Create and run the game
    game_state = create_game(config, strategies)
    game_state = start_game(game_state, strategies)

    # Generate summary and print results
    summary = generate_summary(game_state)
    print_summary(summary)

    # Build a result record and save to the result log
    serialized = serialize_game(game_state)
    result = GameResult(
        config=serialized.get("config"),
        rankings=[
            {
                "rank": rm.rank,
                "model_id": rm.model_id,
                "strategy_name": rm.strategy_name,
                "final_score": rm.final_score,
                "turns_taken": rm.turns_taken,
                "nodes_visited": rm.nodes_visited,
                "cause_of_termination": rm.cause_of_termination.name,
            }
            for rm in summary.rankings
        ],
        graph_stats=summary.graph_stats,
        total_turns=summary.total_turns,
        full_state=serialized,
    )

    store = JsonFileResultStore(path=args.results_file)
    game_id = store.save(result)

    print(f"  Result saved (game_id: {game_id})")
    print(f"  Results log: {args.results_file}")
    print()


if __name__ == "__main__":
    main()
