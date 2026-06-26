"""Property 20: Final ranking correctness.

**Feature: graph-model-arena, Property 20: Final ranking correctness**
**Validates: Requirements 5.5**

For any completed game, models SHALL be ranked by final score in descending order,
with ties broken by fewer turns taken (ascending).
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from graph_model_arena.models import ModelState
from graph_model_arena.score_manager import compute_final_rankings


# ---------------------------------------------------------------------------
# Custom strategies
# ---------------------------------------------------------------------------

STRATEGY_NAMES = [
    "random_walker",
    "greedy_explorer",
    "shortest_path",
    "cautious_navigator",
    "risk_taker",
    "clue_seeker",
    "sprint_runner",
    "balanced_strategist",
]


@st.composite
def arbitrary_model_state(draw: st.DrawFn) -> ModelState:
    """Generate a random ModelState representing a completed model."""
    model_id = draw(
        st.text(
            min_size=1,
            max_size=10,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        )
    )
    strategy_name = draw(st.sampled_from(STRATEGY_NAMES))
    current_node = draw(
        st.text(
            min_size=1,
            max_size=5,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        )
    )
    score = draw(st.integers(min_value=-100, max_value=500))
    turns_taken = draw(st.integers(min_value=1, max_value=200))
    has_finished = draw(st.booleans())
    visited_nodes = draw(
        st.frozensets(
            st.text(
                min_size=1,
                max_size=5,
                alphabet=st.characters(whitelist_categories=("L", "N")),
            ),
            min_size=1,
            max_size=15,
        )
    )

    return ModelState(
        model_id=model_id,
        strategy_name=strategy_name,
        current_node=current_node,
        score=score,
        has_finished=has_finished,
        turns_taken=turns_taken,
        visited_nodes=set(visited_nodes),
    )


@st.composite
def arbitrary_model_states_list(draw: st.DrawFn) -> list[ModelState]:
    """Generate a list of 2-8 ModelStates with unique model_ids."""
    num_models = draw(st.integers(min_value=2, max_value=8))
    models: list[ModelState] = []
    used_ids: set[str] = set()

    for i in range(num_models):
        model = draw(arbitrary_model_state())
        # Ensure unique model_id by appending index suffix
        unique_id = f"{model.model_id}_{i}"
        model.model_id = unique_id
        models.append(model)

    return models


# ---------------------------------------------------------------------------
# Property 20: Final ranking is sorted by score descending
# **Validates: Requirements 5.5**
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(model_states=arbitrary_model_states_list())
def test_property_20_rankings_sorted_by_score_descending(
    model_states: list[ModelState],
) -> None:
    """Rankings SHALL be ordered by final score in descending order."""
    rankings = compute_final_rankings(model_states)

    for i in range(len(rankings) - 1):
        assert rankings[i].final_score >= rankings[i + 1].final_score, (
            f"Rank {rankings[i].rank} (score={rankings[i].final_score}) should have "
            f"score >= rank {rankings[i + 1].rank} (score={rankings[i + 1].final_score})"
        )


# ---------------------------------------------------------------------------
# Property 20: Ties are broken by fewer turns taken (ascending)
# **Validates: Requirements 5.5**
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(model_states=arbitrary_model_states_list())
def test_property_20_ties_broken_by_turns_ascending(
    model_states: list[ModelState],
) -> None:
    """When scores are tied, models with fewer turns_taken SHALL rank higher."""
    rankings = compute_final_rankings(model_states)

    for i in range(len(rankings) - 1):
        if rankings[i].final_score == rankings[i + 1].final_score:
            assert rankings[i].turns_taken <= rankings[i + 1].turns_taken, (
                f"Tied scores: rank {rankings[i].rank} (turns={rankings[i].turns_taken}) "
                f"should have turns_taken <= rank {rankings[i + 1].rank} "
                f"(turns={rankings[i + 1].turns_taken})"
            )


# ---------------------------------------------------------------------------
# Property 20: Rank numbering is correct (1, 2, 3, ...)
# **Validates: Requirements 5.5**
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(model_states=arbitrary_model_states_list())
def test_property_20_rank_numbering_sequential(
    model_states: list[ModelState],
) -> None:
    """Rankings SHALL be numbered sequentially starting from 1."""
    rankings = compute_final_rankings(model_states)

    assert len(rankings) == len(model_states), (
        f"Number of ranked models ({len(rankings)}) should equal "
        f"number of input models ({len(model_states)})"
    )

    for i, ranked_model in enumerate(rankings, start=1):
        assert ranked_model.rank == i, (
            f"Expected rank {i}, got rank {ranked_model.rank}"
        )


# ---------------------------------------------------------------------------
# Property 20: All input models appear exactly once in rankings
# **Validates: Requirements 5.5**
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(model_states=arbitrary_model_states_list())
def test_property_20_all_models_ranked_exactly_once(
    model_states: list[ModelState],
) -> None:
    """Every input model SHALL appear exactly once in the final rankings."""
    rankings = compute_final_rankings(model_states)

    input_ids = {m.model_id for m in model_states}
    ranked_ids = {r.model_id for r in rankings}

    assert input_ids == ranked_ids, (
        f"Input model IDs {input_ids} should match ranked IDs {ranked_ids}"
    )
