# Graph Model Arena

A competitive AI playground where 2-8 AI models navigate a dynamically generated graph from a starting node to an ending node. Each game features randomized topology, fog-of-war visibility, and special node types (traps, checkpoints, clues, maps, points) — creating a rich strategic environment where no two competitions are alike.

## Setup

Requires Python 3.10+.

```bash
pip install hypothesis pytest
```

No other dependencies are needed — the project uses only the standard library plus `hypothesis` for property-based testing and `pytest` for the test runner.

## Running a Game

```bash
python main.py
```

### CLI Options

| Flag | Description | Default |
|------|-------------|---------|
| `--num-nodes` | Number of graph nodes (20-200) | 30 |
| `--num-models` | Number of competing models (2-8) | 4 |
| `--max-turns` | Maximum turns before game ends | 50 |
| `--edge-density` | Edge density beyond spanning tree (0.0-1.0) | 0.3 |
| `--results-file` | Results log file path | game_results.json |
| `--seed` | Random seed for reproducibility | None |



## Configuration

All game parameters can be passed via CLI flags or by editing the defaults in code. Here's the full set of configurable options:

### Graph Configuration

| Parameter | CLI Flag | Range | Default | Description |
|-----------|----------|-------|---------|-------------|
| num_nodes | `--num-nodes` | 20-200 | 30 | Number of nodes in the graph |
| edge_density | `--edge-density` | 0.0-1.0 | 0.3 | Proportion of extra edges beyond the spanning tree |
| trap_probability | — | 0.0-1.0 | 0.1 | Chance a node becomes a trap |
| clue_probability | — | 0.0-1.0 | 0.1 | Chance a node becomes a clue node |
| map_probability | — | 0.0-1.0 | 0.1 | Chance a node becomes a map node |
| checkpoint_probability | — | 0.0-1.0 | 0.1 | Chance a node becomes a checkpoint |
| points_probability | — | 0.0-1.0 | 0.2 | Chance a node becomes a points node |
| obstacle_density | — | 0.0-1.0 | 0.1 | Proportion of edges that are obstructed |
| map_reveal_depth | — | 1-3 | 2 | How many hops a map node reveals |

### Game Configuration

| Parameter | CLI Flag | Range | Default | Description |
|-----------|----------|-------|---------|-------------|
| num_models | `--num-models` | 2-8 | 4 | Number of AI models competing |
| max_turns | `--max-turns` | >0 | 50 | Turn limit before game ends |
| move_timeout_seconds | — | >0 | 5.0 | Seconds a model has to decide |
| completion_bonus_multiplier | — | any float | 1.0 | Multiplier for the finish bonus |
| death_penalty | — | any int | 10 | Score deducted on trap death (no checkpoint) |
| trap_respawn_penalty | — | any int | 5 | Score deducted on trap respawn (with checkpoint) |
| invalid_move_penalty | — | any int | 1 | Score deducted for invalid moves |

### Changing Parameters Not Exposed via CLI

Parameters without a CLI flag can be set programmatically. Edit `main.py` or write your own script:

```python
from graph_model_arena.models import GameConfig, GraphConfig
from graph_model_arena.game_engine import create_game, start_game
from graph_model_arena.game_reporter import generate_summary, serialize_game
from graph_model_arena.model_interface import ModelRegistry
from graph_model_arena.strategies import *

# Customize the graph
graph_config = GraphConfig(
    num_nodes=80,
    edge_density=0.4,
    trap_probability=0.15,
    clue_probability=0.05,
    map_probability=0.1,
    checkpoint_probability=0.15,
    points_probability=0.25,
    obstacle_density=0.2,
    map_reveal_depth=3,
)

# Customize the game
config = GameConfig(
    graph_config=graph_config,
    num_models=6,
    max_turns=100,
    move_timeout_seconds=3.0,
    completion_bonus_multiplier=2.0,
    death_penalty=15,
    trap_respawn_penalty=8,
    invalid_move_penalty=2,
)

# Register strategies and run
registry = ModelRegistry()
strategies_to_use = [RandomWalker, GreedyExplorer, ShortestPath,
                     CautiousNavigator, RiskTaker, ClueSeeker]
for cls in strategies_to_use:
    instance = cls()
    registry.register(instance, model_id=instance.name)

game_state = create_game(config, registry.get_all())
game_state = start_game(game_state, registry.get_all())

summary = generate_summary(game_state)
for rm in summary.rankings:
    print(f"#{rm.rank} {rm.strategy_name}: {rm.final_score} pts")
```

### Quick Start Examples

```bash
# Default game (4 models, 30 nodes, 50 turns)
python main.py

# Larger arena with all 8 models
python main.py --num-models 8 --num-nodes 100 --max-turns 100

# Small fast game for testing
python main.py --num-models 2 --num-nodes 20 --max-turns 20

# Reproducible game with a fixed seed
python main.py --seed 12345

# Dense graph with more edges and obstacles
python main.py --num-nodes 60 --edge-density 0.6
```

## Built-in Strategies

| Strategy | Description |
|----------|-------------|
| Random_Walker | Picks a random adjacent node each turn |
| Greedy_Explorer | Prioritizes unvisited nodes and highest-value points |
| Shortest_Path | Dijkstra on visible graph toward the end node |
| Cautious_Navigator | Avoids unknown nodes, prioritizes checkpoints |
| Risk_Taker | Explores aggressively, ignores traps, seeks points |
| Clue_Seeker | Prioritizes clue and map nodes for information |
| Sprint_Runner | Beelines to the end node, ignores points |
| Balanced_Strategist | Switches between explore/collect/goal-seek by phase |

## Creating a Custom Strategy

Subclass `ModelStrategy` and implement `decide_move`:

```python
from graph_model_arena.model_interface import ModelStrategy
from graph_model_arena.models import ModelView

class MyStrategy(ModelStrategy):
    @property
    def name(self) -> str:
        return "My_Strategy"

    def decide_move(self, state: ModelView) -> str:
        # state.current_node — your current position
        # state.visible_nodes — dict of node_id -> Node (with type info)
        # state.visible_edges — list of (source, target, cost, obstructed)
        # state.current_score, state.turn_number, state.has_checkpoint
        return "target_node_id"
```

## Running Tests

```bash
pytest
```

This runs all unit tests and property-based tests (~200 tests).

## Project Structure

```
graph_model_arena/
├── models.py              # Data models (Node, Edge, Graph, GameState, etc.)
├── graph_generator.py     # Random graph generation with connectivity guarantees
├── game_engine.py         # Game lifecycle (create, start, end conditions)
├── turn_manager.py        # Turn execution and move collection
├── move_validator.py      # Move adjacency and obstruction checks
├── state_resolver.py      # Simultaneous move resolution
├── node_effects.py        # Trap, clue, map, checkpoint, points processing
├── visibility_manager.py  # Per-model fog-of-war
├── score_manager.py       # Scoring and final rankings
├── game_reporter.py       # Summary generation and serialization
├── model_interface.py     # ModelStrategy ABC and ModelRegistry
└── strategies/            # 8 built-in AI strategies
tests/                     # Unit and property-based tests
main.py                    # CLI entry point
```

## Game Output

After each game, results are printed to stdout and appended to a results log file (`game_results.json` by default). Each entry includes a unique `game_id`, timestamp, config used, rankings, graph stats, and the full serialized game state. This makes it easy to track results across multiple runs.

The result store uses a `ResultStore` protocol, so migrating to a database later is straightforward — implement the protocol for your DB of choice and swap it in:

```python
from graph_model_arena.result_store import ResultStore, GameResult

class PostgresResultStore:
    """Drop-in replacement backed by PostgreSQL."""

    def save(self, result: GameResult) -> str:
        # INSERT INTO game_results ...
        ...

    def get(self, result_id: str) -> GameResult | None:
        # SELECT * FROM game_results WHERE game_id = ...
        ...

    def list_all(self) -> list[GameResult]:
        # SELECT * FROM game_results ORDER BY timestamp DESC
        ...
```

## Running with Docker

Build and run using Docker Compose:

```bash
# Run a game with default settings
docker compose up arena

# Run with custom CLI options
docker compose run arena --num-models 6 --num-nodes 80 --seed 42

# Run the test suite
docker compose --profile testing up test
```

Or use Docker directly:

```bash
# Build the image
docker build -t graph-model-arena .

# Run a game
docker run --rm graph-model-arena

# Run with options
docker run --rm graph-model-arena --num-models 8 --max-turns 100

# Run tests
docker run --rm --entrypoint pytest graph-model-arena -v
```

Game results are persisted to the host via a volume mount in the Compose setup, so `game_results.json` stays updated between runs.

## Frontend Visualization

An optional React single-page application that visualizes completed game results as an interactive graph. Upload your `game_results.json` file and explore games turn by turn with playback controls, a live scoreboard, and an event log.

### Features

- Force-directed graph rendering with color-coded node types and edge styles
- Turn-by-turn playback with variable speed (1x–4x)
- Player markers showing positions on the graph at each turn
- Scoreboard tracking scores and rankings in real time
- Event log with click-to-jump navigation
- Node highlight animation when events occur
- Responsive layout (stacks on mobile, side-by-side on desktop)

### Setup

Requires Node.js 18+ and npm.

```bash
cd frontend
npm install
```

### Running

```bash
cd frontend
npm run dev
```

Opens at `http://localhost:5173`. Upload a `game_results.json` file to start visualizing.

### Running Tests

```bash
cd frontend
npm test
```

### Building for Production

```bash
cd frontend
npm run build
```

Output goes to `frontend/dist/` — serve it with any static file server.

### Project Structure

```
frontend/
├── src/
│   ├── components/          # React UI components
│   │   ├── FileUploader.jsx
│   │   ├── GameSelector.jsx
│   │   ├── GraphCanvas.jsx
│   │   ├── PlaybackControls.jsx
│   │   ├── Scoreboard.jsx
│   │   ├── EventLog.jsx
│   │   └── PlayerLegend.jsx
│   ├── context/
│   │   └── GameContext.jsx  # State management (useReducer)
│   ├── utils/
│   │   ├── parseGameData.js        # JSON parser and validator
│   │   └── computeTurnSnapshots.js # Turn state derivation
│   ├── constants/
│   │   └── colors.js        # Node and player color palettes
│   ├── App.jsx              # Root component with routing
│   └── main.jsx             # Entry point
├── package.json
├── vite.config.js
└── index.html
```

The frontend has zero coupling to the Python backend — it only reads the `game_results.json` file format produced by the game engine.
