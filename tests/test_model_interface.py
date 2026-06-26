"""Unit tests for model_interface module."""

from __future__ import annotations

import pytest

from graph_model_arena.model_interface import ModelRegistry, ModelStrategy
from graph_model_arena.models import ModelView, Node, NodeType


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


class DummyStrategy(ModelStrategy):
    """A minimal concrete strategy for testing."""

    def decide_move(self, state: ModelView) -> str:
        # Just pick the first visible neighbor
        if state.visible_edges:
            return state.visible_edges[0][1]
        return state.current_node


class NamedStrategy(ModelStrategy):
    """A strategy with a custom name."""

    @property
    def name(self) -> str:
        return "CustomName"

    def decide_move(self, state: ModelView) -> str:
        return state.current_node


# ---------------------------------------------------------------------------
# ModelStrategy tests
# ---------------------------------------------------------------------------


class TestModelStrategy:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            ModelStrategy()  # type: ignore[abstract]

    def test_concrete_subclass_has_default_name(self):
        strategy = DummyStrategy()
        assert strategy.name == "DummyStrategy"

    def test_concrete_subclass_can_override_name(self):
        strategy = NamedStrategy()
        assert strategy.name == "CustomName"

    def test_decide_move_is_callable(self):
        strategy = DummyStrategy()
        view = ModelView(
            current_node="A",
            visible_nodes={"A": Node(id="A", node_type=NodeType.START)},
            visible_edges=[("A", "B", 1, False)],
            current_score=0,
            turn_number=1,
            has_checkpoint=False,
            checkpoint_node=None,
        )
        result = strategy.decide_move(view)
        assert result == "B"


# ---------------------------------------------------------------------------
# ModelRegistry tests
# ---------------------------------------------------------------------------


class TestModelRegistry:
    def test_register_assigns_unique_id(self):
        registry = ModelRegistry()
        s1 = DummyStrategy()
        s2 = DummyStrategy()
        id1 = registry.register(s1)
        id2 = registry.register(s2)
        assert id1 != id2
        assert registry.count == 2

    def test_register_with_custom_id(self):
        registry = ModelRegistry()
        strategy = DummyStrategy()
        model_id = registry.register(strategy, model_id="my_model")
        assert model_id == "my_model"
        assert registry.get("my_model") is strategy

    def test_register_duplicate_id_raises(self):
        registry = ModelRegistry()
        s1 = DummyStrategy()
        s2 = DummyStrategy()
        registry.register(s1, model_id="dup")
        with pytest.raises(ValueError, match="already registered"):
            registry.register(s2, model_id="dup")

    def test_get_returns_none_for_unknown(self):
        registry = ModelRegistry()
        assert registry.get("nonexistent") is None

    def test_get_all_returns_copy(self):
        registry = ModelRegistry()
        s1 = DummyStrategy()
        registry.register(s1, model_id="m1")
        all_strategies = registry.get_all()
        assert "m1" in all_strategies
        # Mutating the copy doesn't affect the registry
        all_strategies["m2"] = DummyStrategy()
        assert registry.count == 1

    def test_unregister_existing(self):
        registry = ModelRegistry()
        strategy = DummyStrategy()
        registry.register(strategy, model_id="to_remove")
        assert registry.unregister("to_remove") is True
        assert registry.get("to_remove") is None
        assert registry.count == 0

    def test_unregister_nonexistent(self):
        registry = ModelRegistry()
        assert registry.unregister("ghost") is False

    def test_clear(self):
        registry = ModelRegistry()
        for i in range(5):
            registry.register(DummyStrategy(), model_id=f"m{i}")
        assert registry.count == 5
        registry.clear()
        assert registry.count == 0
        assert registry.model_ids == []

    def test_model_ids_list(self):
        registry = ModelRegistry()
        registry.register(DummyStrategy(), model_id="alpha")
        registry.register(DummyStrategy(), model_id="beta")
        assert set(registry.model_ids) == {"alpha", "beta"}

    def test_generated_id_includes_strategy_name(self):
        registry = ModelRegistry()
        strategy = DummyStrategy()
        model_id = registry.register(strategy)
        assert model_id.startswith("DummyStrategy_")

    def test_all_generated_ids_are_unique(self):
        """Requirement 6.3: unique model identifiers."""
        registry = ModelRegistry()
        ids = set()
        for _ in range(50):
            model_id = registry.register(DummyStrategy())
            ids.add(model_id)
        assert len(ids) == 50
