"""Core data models, enums, and types for Graph Model Arena."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class NodeType(Enum):
    NORMAL = auto()
    START = auto()
    END = auto()
    TRAP = auto()
    CLUE = auto()
    MAP = auto()
    CHECKPOINT = auto()
    POINTS = auto()


class EventType(Enum):
    MOVE = auto()
    TRAP_RESPAWN_START = auto()
    TRAP_RESPAWN_CHECKPOINT = auto()
    CLUE_RECEIVED = auto()
    MAP_REVEALED = auto()
    POINTS_COLLECTED = auto()
    CHECKPOINT_ACTIVATED = auto()
    INVALID_MOVE = auto()
    TIMEOUT = auto()
    GAME_FINISHED = auto()
    GAME_ENDED_BY_TURN_LIMIT = auto()


class TerminationCause(Enum):
    FINISHED = auto()
    TURN_LIMIT = auto()


# ---------------------------------------------------------------------------
# Graph models
# ---------------------------------------------------------------------------

@dataclass
class Node:
    id: str
    node_type: NodeType
    point_value: int = 0  # only meaningful for POINTS nodes (1-10)


@dataclass
class Edge:
    source: str
    target: str
    cost: int  # 1-10
    obstructed: bool = False


@dataclass
class Graph:
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[Edge] = field(default_factory=list)
    adjacency: dict[str, list[tuple[str, Edge]]] = field(default_factory=dict)
    start_node: str = ""
    end_node: str = ""


# ---------------------------------------------------------------------------
# Configuration models
# ---------------------------------------------------------------------------


@dataclass
class GraphConfig:
    num_nodes: int = 20
    edge_density: float = 0.3
    trap_probability: float = 0.1
    clue_probability: float = 0.1
    map_probability: float = 0.1
    checkpoint_probability: float = 0.1
    points_probability: float = 0.2
    obstacle_density: float = 0.1
    map_reveal_depth: int = 2
    min_point_value: int = 1
    max_point_value: int = 10

    def validate(self) -> None:
        """Validate all configuration values, raising ValueError if invalid."""
        if not (20 <= self.num_nodes <= 200):
            raise ValueError(
                f"num_nodes must be between 20 and 200, got {self.num_nodes}"
            )
        for name in (
            "trap_probability",
            "clue_probability",
            "map_probability",
            "checkpoint_probability",
            "points_probability",
        ):
            val = getattr(self, name)
            if not (0 <= val <= 1):
                raise ValueError(f"{name} must be between 0 and 1, got {val}")
        if not (0 <= self.edge_density <= 1):
            raise ValueError(
                f"edge_density must be between 0 and 1, got {self.edge_density}"
            )
        if not (0 <= self.obstacle_density <= 1):
            raise ValueError(
                f"obstacle_density must be between 0 and 1, got {self.obstacle_density}"
            )
        if not (1 <= self.map_reveal_depth <= 3):
            raise ValueError(
                f"map_reveal_depth must be between 1 and 3, got {self.map_reveal_depth}"
            )




@dataclass
class GameConfig:
    graph_config: GraphConfig = field(default_factory=GraphConfig)
    num_models: int = 4
    max_turns: int = 100
    move_timeout_seconds: float = 5.0
    completion_bonus_multiplier: float = 1.0
    death_penalty: int = 10
    invalid_move_penalty: int = 1
    trap_respawn_penalty: int = 5

    def validate(self) -> None:
        """Validate all configuration values, raising ValueError if invalid."""
        self.graph_config.validate()
        if not (2 <= self.num_models <= 8):
            raise ValueError(
                f"num_models must be between 2 and 8, got {self.num_models}"
            )
        if self.max_turns <= 0:
            raise ValueError(
                f"max_turns must be greater than 0, got {self.max_turns}"
            )
        if self.move_timeout_seconds <= 0:
            raise ValueError(
                f"move_timeout_seconds must be greater than 0, got {self.move_timeout_seconds}"
            )


# ---------------------------------------------------------------------------
# Game state models
# ---------------------------------------------------------------------------

@dataclass
class ModelState:
    model_id: str
    strategy_name: str
    current_node: str
    score: int = 0
    has_finished: bool = False
    active_checkpoint: str | None = None
    visited_nodes: set[str] = field(default_factory=set)
    visible_nodes: set[str] = field(default_factory=set)
    visible_edges: set[tuple[str, str]] = field(default_factory=set)
    turns_taken: int = 0
    trap_deaths: int = 0


@dataclass
class GameEvent:
    turn: int
    model_id: str
    event_type: EventType
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class GameState:
    graph: Graph = field(default_factory=Graph)
    models: dict[str, ModelState] = field(default_factory=dict)
    current_turn: int = 0
    max_turns: int = 100
    config: GameConfig = field(default_factory=GameConfig)
    event_log: list[GameEvent] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Output / reporting models
# ---------------------------------------------------------------------------

@dataclass
class RankedModel:
    rank: int
    model_id: str
    strategy_name: str
    final_score: int
    turns_taken: int
    nodes_visited: int
    cause_of_termination: TerminationCause
    path: list[str] = field(default_factory=list)


@dataclass
class GameSummary:
    graph: Graph = field(default_factory=Graph)
    rankings: list[RankedModel] = field(default_factory=list)
    total_turns: int = 0
    graph_stats: dict[str, Any] = field(default_factory=dict)
    event_log: list[GameEvent] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Move / turn models
# ---------------------------------------------------------------------------

@dataclass
class ModelView:
    current_node: str = ""
    visible_nodes: dict[str, Node] = field(default_factory=dict)
    visible_edges: list[tuple[str, str, int, bool]] = field(default_factory=list)
    current_score: int = 0
    turn_number: int = 0
    has_checkpoint: bool = False
    checkpoint_node: str | None = None


@dataclass
class MoveResult:
    valid: bool
    reason: str = ""


@dataclass
class ValidatedMove:
    model_id: str
    target_node: str
    valid: bool
    reason: str = ""
