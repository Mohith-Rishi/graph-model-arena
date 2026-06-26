"""Model Interface — abstract base class and registry for AI model strategies.

Provides:
- ModelStrategy: Abstract base class that all AI strategies must implement.
- ModelRegistry: Registry for model strategy instances with unique ID assignment.

Requirements: 6.1, 6.2, 6.3
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod

from graph_model_arena.models import ModelView


class ModelStrategy(ABC):
    """Abstract base class for AI model strategies.

    All competing models must subclass this and implement `decide_move`.
    """

    @property
    def name(self) -> str:
        """Human-readable name identifying this strategy.

        Defaults to the class name. Subclasses may override for a custom name.
        """
        return self.__class__.__name__

    @abstractmethod
    def decide_move(self, state: ModelView) -> str:
        """Given the model's visible state, return the target node ID.

        Args:
            state: A ModelView containing the model's current node, visible
                   graph subset, current score, turn number, and checkpoint status.

        Returns:
            The identifier of the target node to move to.
        """
        ...


class ModelRegistry:
    """Registry for model strategy instances with unique ID assignment.

    Handles:
    - Registering model strategy instances
    - Assigning unique IDs to models
    - Retrieving registered models by ID
    """

    def __init__(self) -> None:
        self._strategies: dict[str, ModelStrategy] = {}

    def register(
        self, strategy: ModelStrategy, model_id: str | None = None
    ) -> str:
        """Register a model strategy and assign a unique ID.

        Args:
            strategy: A ModelStrategy instance to register.
            model_id: Optional custom ID. If not provided, a unique ID is generated.

        Returns:
            The assigned model ID.

        Raises:
            ValueError: If the provided model_id is already registered.
        """
        if model_id is None:
            model_id = self._generate_id(strategy)

        if model_id in self._strategies:
            raise ValueError(
                f"Model ID '{model_id}' is already registered"
            )

        self._strategies[model_id] = strategy
        return model_id

    def get(self, model_id: str) -> ModelStrategy | None:
        """Retrieve a registered strategy by model ID.

        Returns None if the model_id is not registered.
        """
        return self._strategies.get(model_id)

    def get_all(self) -> dict[str, ModelStrategy]:
        """Return a copy of all registered strategies keyed by model ID."""
        return dict(self._strategies)

    def unregister(self, model_id: str) -> bool:
        """Remove a model from the registry.

        Returns True if the model was found and removed, False otherwise.
        """
        if model_id in self._strategies:
            del self._strategies[model_id]
            return True
        return False

    def clear(self) -> None:
        """Remove all registered models."""
        self._strategies.clear()

    @property
    def count(self) -> int:
        """Number of currently registered models."""
        return len(self._strategies)

    @property
    def model_ids(self) -> list[str]:
        """List of all registered model IDs."""
        return list(self._strategies.keys())

    def _generate_id(self, strategy: ModelStrategy) -> str:
        """Generate a unique model ID based on strategy name and a short UUID."""
        short_uuid = uuid.uuid4().hex[:8]
        return f"{strategy.name}_{short_uuid}"
