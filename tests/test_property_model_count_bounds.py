"""Property 23: Model count bounds.

**Feature: graph-model-arena, Property 23: Model count bounds**
**Validates: Requirements 6.4**

For any GameConfig, the game SHALL accept configurations with 2-8 models
and reject configurations outside this range.
"""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from graph_model_arena.models import GameConfig, GraphConfig


@settings(max_examples=100)
@given(num_models=st.integers(min_value=2, max_value=8))
def test_valid_model_counts_are_accepted(num_models: int) -> None:
    """Valid model counts (2-8) must be accepted without error."""
    config = GameConfig(num_models=num_models)
    config.validate()  # should not raise


@settings(max_examples=100)
@given(
    num_models=st.one_of(
        st.integers(max_value=1),
        st.integers(min_value=9),
    )
)
def test_invalid_model_counts_are_rejected(num_models: int) -> None:
    """Model counts outside [2, 8] must raise ValueError."""
    config = GameConfig(num_models=num_models)
    with pytest.raises(ValueError, match="num_models"):
        config.validate()
