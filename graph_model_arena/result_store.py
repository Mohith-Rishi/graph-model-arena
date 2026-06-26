"""Result Store — abstraction for persisting game results.

Provides a protocol-based interface for storing game results so the backend
can be swapped from JSON file to a database without changing calling code.

To migrate to a database later, implement a new class that satisfies the
ResultStore protocol (e.g. PostgresResultStore, SQLiteResultStore) and pass
it to main instead of JsonFileResultStore.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol


class ResultStore(Protocol):
    """Protocol for game result persistence.

    Implement this interface to back the result log with any storage:
    JSON file, SQLite, PostgreSQL, DynamoDB, etc.
    """

    def save(self, result: GameResult) -> str:
        """Persist a game result. Returns the result ID."""
        ...

    def get(self, result_id: str) -> GameResult | None:
        """Retrieve a single result by ID."""
        ...

    def list_all(self) -> list[GameResult]:
        """Retrieve all stored results, newest first."""
        ...


class GameResult:
    """A single game result record, structured for easy DB migration.

    Fields map cleanly to database columns or document fields.
    """

    def __init__(
        self,
        game_id: str | None = None,
        timestamp: str | None = None,
        config: dict[str, Any] | None = None,
        rankings: list[dict[str, Any]] | None = None,
        graph_stats: dict[str, Any] | None = None,
        total_turns: int = 0,
        full_state: dict[str, Any] | None = None,
    ) -> None:
        self.game_id = game_id or str(uuid.uuid4())
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.config = config or {}
        self.rankings = rankings or []
        self.graph_stats = graph_stats or {}
        self.total_turns = total_turns
        self.full_state = full_state  # optional — the full serialized game state

    def to_dict(self) -> dict[str, Any]:
        """Convert to a plain dictionary (JSON-serializable)."""
        return {
            "game_id": self.game_id,
            "timestamp": self.timestamp,
            "config": self.config,
            "rankings": self.rankings,
            "graph_stats": self.graph_stats,
            "total_turns": self.total_turns,
            "full_state": self.full_state,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GameResult:
        """Reconstruct a GameResult from a dictionary."""
        return cls(
            game_id=data.get("game_id"),
            timestamp=data.get("timestamp"),
            config=data.get("config"),
            rankings=data.get("rankings"),
            graph_stats=data.get("graph_stats"),
            total_turns=data.get("total_turns", 0),
            full_state=data.get("full_state"),
        )


class JsonFileResultStore:
    """JSON file-backed result store. Appends results to a single log file.

    Each game result is stored as an entry in a JSON array. The file is
    created on first write if it doesn't exist.

    To migrate to a database:
    1. Create a new class implementing the ResultStore protocol
    2. Replace JsonFileResultStore with your new class where instantiated
    3. Optionally import existing results via list_all() -> new_store.save()
    """

    def __init__(self, path: str = "game_results.json") -> None:
        self._path = Path(path)

    def save(self, result: GameResult) -> str:
        """Append a game result to the log file. Returns the game_id."""
        results = self._load_all()
        results.append(result.to_dict())
        self._write_all(results)
        return result.game_id

    def get(self, result_id: str) -> GameResult | None:
        """Find a result by game_id."""
        for entry in self._load_all():
            if entry.get("game_id") == result_id:
                return GameResult.from_dict(entry)
        return None

    def list_all(self) -> list[GameResult]:
        """Return all results, newest first."""
        entries = self._load_all()
        entries.reverse()
        return [GameResult.from_dict(e) for e in entries]

    def _load_all(self) -> list[dict[str, Any]]:
        """Load the results array from disk."""
        if not self._path.exists():
            return []
        text = self._path.read_text(encoding="utf-8").strip()
        if not text:
            return []
        return json.loads(text)

    def _write_all(self, results: list[dict[str, Any]]) -> None:
        """Write the full results array to disk."""
        self._path.write_text(
            json.dumps(results, indent=2),
            encoding="utf-8",
        )
