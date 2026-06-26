"""Property 11: Points collection — first visit vs. revisit.

**Feature: graph-model-arena, Property 11: Points collection — first visit vs. revisit**
**Validates: Requirements 2.6, 2.7, 5.2**

For any model entering a Points_Node, if the node is not in the model's visited set,
the model's score SHALL increase by the node's point_value; if the node is already in
the model's visited set, the model's score SHALL remain unchanged.
"""

from __future__ import annotations

import copy

from hypothesis import given, settings
from hypothesis import strategies as st

from graph_model_arena.models import ModelState, Node, NodeType
from graph_model_arena.score_manager import apply_points


# ---------------------------------------------------------------------------
# Custom strategies
# ---------------------------------------------------------------------------

@st.composite
def arbitrary_points_node(draw: st.DrawFn) -> Node:
    """Generate a random Points_Node with a valid point_value (1-10)."""
    node_id = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))))
    point_value = draw(st.integers(min_value=1, max_value=10))
    return Node(id=node_id, node_type=NodeType.POINTS, point_value=point_value)


@st.composite
def arbitrary_model_state(draw: st.DrawFn) -> ModelState:
    """Generate a random ModelState."""
    model_id = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))))
    strategy_name = draw(st.sampled_from(["random_walker", "greedy_explorer", "shortest_path"]))
    current_node = draw(st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))))
    score = draw(st.integers(min_value=-100, max_value=1000))
    visited_nodes = draw(
        st.frozensets(
            st.text(min_size=1, max_size=10, alphabet=st.characters(whitelist_categories=("L", "N"))),
            min_size=0,
            max_size=20,
        )
    )
    return ModelState(
        model_id=model_id,
        strategy_name=strategy_name,
        current_node=current_node,
        score=score,
        visited_nodes=set(visited_nodes),
    )


# ---------------------------------------------------------------------------
# Property 11: First visit increases score by point_value
# **Validates: Requirements 2.6, 5.2**
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(model_state=arbitrary_model_state(), points_node=arbitrary_points_node())
def test_property_11_first_visit_increases_score(
    model_state: ModelState, points_node: Node
) -> None:
    """On first visit to a Points_Node (not in visited set), score increases by point_value."""
    # Ensure the node is NOT in visited set (first visit)
    model_state.visited_nodes.discard(points_node.id)
    score_before = model_state.score

    apply_points(model_state, points_node)

    assert model_state.score == score_before + points_node.point_value


# ---------------------------------------------------------------------------
# Property 11: Revisit does not change score
# **Validates: Requirements 2.7, 5.2**
# ---------------------------------------------------------------------------

@settings(max_examples=200)
@given(model_state=arbitrary_model_state(), points_node=arbitrary_points_node())
def test_property_11_revisit_does_not_change_score(
    model_state: ModelState, points_node: Node
) -> None:
    """On revisit to a Points_Node (already in visited set), score remains unchanged."""
    # Ensure the node IS in visited set (revisit)
    model_state.visited_nodes.add(points_node.id)
    score_before = model_state.score

    apply_points(model_state, points_node)

    assert model_state.score == score_before
