"""Property tests for Visibility (Properties 13-14).

**Feature: graph-model-arena, Properties 13-14: Visibility**
**Validates: Requirements 3.2, 3.5, 6.1**

Property 13: Movement expands visibility
Property 14: ModelView accuracy
"""

from __future__ import annotations

import copy
from collections import deque

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from graph_model_arena.models import (
    Edge,
    GameConfig,
    GameState,
    Graph,
    GraphConfig,
    ModelState,
    ModelView,
    Node,
    NodeType,
    ValidatedMove,
)
from graph_model_arena.state_resolver import resolve_moves
from graph_model_arena.turn_manager import _build_model_view
from graph_model_arena.visibility_manager import (
    expand_visibility,
    get_visible_graph,
    initialize_visibility,
)


# ---------------------------------------------------------------------------
# Custom strategies for generating valid graphs and game states
# ---------------------------------------------------------------------------

_NODE_ID_ALPHABET = st.characters(whitelist_categories=("L", "N"))


@st.composite
def arbitrary_linear_graph(draw: st.DrawFn) -> tuple[Graph, list[str]]:
    """Generate a linear graph: start -> n0 -> n1 -> ... -> end.

    Returns (graph, list_of_all_node_ids_in_order).
    The chain length (excluding start/end) is between 2 and 8.
    """
    num_middle = draw(st.integers(min_value=2, max_value=8))
    node_ids = ["start"] + [f"n{i}" for i in range(num_middle)] + ["end"]

    node_types = [NodeType.NORMAL] * num_middle
    # Assign some variety to middle nodes
    for i in range(num_middle):
        node_types[i] = draw(
            st.sampled_from(
                [NodeType.NORMAL, NodeType.CHECKPOINT, NodeType.POINTS, NodeType.CLUE]
            )
        )

    nodes: dict[str, Node] = {
        "start": Node(id="start", node_type=NodeType.START),
        "end": Node(id="end", node_type=NodeType.END),
    }
    for i in range(num_middle):
        nid = f"n{i}"
        point_value = draw(st.integers(min_value=1, max_value=10)) if node_types[i] == NodeType.POINTS else 0
        nodes[nid] = Node(id=nid, node_type=node_types[i], point_value=point_value)

    # Build edges as a chain
    edges: list[Edge] = []
    adjacency: dict[str, list[tuple[str, Edge]]] = {}
    for i in range(len(node_ids) - 1):
        cost = draw(st.integers(min_value=1, max_value=10))
        edge = Edge(source=node_ids[i], target=node_ids[i + 1], cost=cost, obstructed=False)
        edges.append(edge)
        adjacency.setdefault(node_ids[i], []).append((node_ids[i + 1], edge))
        adjacency.setdefault(node_ids[i + 1], []).append((node_ids[i], edge))

    graph = Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node="start",
        end_node="end",
    )
    return graph, node_ids


@st.composite
def arbitrary_connected_graph(draw: st.DrawFn) -> Graph:
    """Generate a connected graph with some branching for richer visibility tests.

    Nodes: start, end, plus 3-10 middle nodes with random edges ensuring connectivity.
    """
    num_middle = draw(st.integers(min_value=3, max_value=10))
    middle_ids = [f"n{i}" for i in range(num_middle)]
    all_ids = ["start"] + middle_ids + ["end"]

    # Create nodes
    nodes: dict[str, Node] = {
        "start": Node(id="start", node_type=NodeType.START),
        "end": Node(id="end", node_type=NodeType.END),
    }
    for nid in middle_ids:
        ntype = draw(
            st.sampled_from(
                [NodeType.NORMAL, NodeType.CHECKPOINT, NodeType.POINTS, NodeType.MAP, NodeType.CLUE]
            )
        )
        point_value = draw(st.integers(min_value=1, max_value=10)) if ntype == NodeType.POINTS else 0
        nodes[nid] = Node(id=nid, node_type=ntype, point_value=point_value)

    # Build a spanning tree to guarantee connectivity (random permutation chain)
    shuffled = draw(st.permutations(middle_ids))
    chain = ["start"] + list(shuffled) + ["end"]

    edges: list[Edge] = []
    adjacency: dict[str, list[tuple[str, Edge]]] = {}

    def add_edge(src: str, tgt: str) -> None:
        cost = draw(st.integers(min_value=1, max_value=10))
        edge = Edge(source=src, target=tgt, cost=cost, obstructed=False)
        edges.append(edge)
        adjacency.setdefault(src, []).append((tgt, edge))
        adjacency.setdefault(tgt, []).append((src, edge))

    # Spanning tree edges
    for i in range(len(chain) - 1):
        add_edge(chain[i], chain[i + 1])

    # Add some random extra edges for branching
    num_extra = draw(st.integers(min_value=1, max_value=min(num_middle, 5)))
    existing_pairs = {(min(e.source, e.target), max(e.source, e.target)) for e in edges}
    for _ in range(num_extra):
        src = draw(st.sampled_from(all_ids))
        tgt = draw(st.sampled_from(all_ids))
        if src == tgt:
            continue
        pair = (min(src, tgt), max(src, tgt))
        if pair in existing_pairs:
            continue
        existing_pairs.add(pair)
        add_edge(src, tgt)

    graph = Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node="start",
        end_node="end",
    )
    return graph


def _get_neighbors(graph: Graph, node_id: str) -> set[str]:
    """Return the set of neighbor node IDs for a given node."""
    return {neighbor_id for neighbor_id, _ in graph.adjacency.get(node_id, [])}


def _make_game_state(
    graph: Graph,
    model_state: ModelState,
    map_reveal_depth: int = 2,
) -> GameState:
    """Helper to build a GameState from a graph and a single model."""
    config = GameConfig(
        graph_config=GraphConfig(map_reveal_depth=map_reveal_depth),
        death_penalty=10,
        trap_respawn_penalty=5,
    )
    return GameState(
        graph=graph,
        models={model_state.model_id: model_state},
        current_turn=1,
        max_turns=100,
        config=config,
    )


# ---------------------------------------------------------------------------
# Property 13: Movement expands visibility
# **Validates: Requirements 3.2**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=5000)
@given(
    graph_data=arbitrary_linear_graph(),
    initial_score=st.integers(min_value=0, max_value=500),
)
def test_property_13_movement_expands_visibility(
    graph_data: tuple[Graph, list[str]],
    initial_score: int,
) -> None:
    """For any model that moves to a new node, the model's visible_nodes SHALL be
    a superset of its previous visible_nodes plus the new node and all of the new
    node's neighbors.

    **Validates: Requirements 3.2**
    """
    graph, node_ids = graph_data

    # Place model at start with initial visibility of start + neighbors
    model = ModelState(
        model_id="model_a",
        strategy_name="test",
        current_node="start",
        score=initial_score,
        visited_nodes={"start"},
        visible_nodes=set(),
        visible_edges=set(),
    )
    game_state = _make_game_state(graph, model)

    # Initialize visibility (start + neighbors)
    initialize_visibility("model_a", graph, game_state)

    # Pick a neighbor of start to move to
    start_neighbors = _get_neighbors(graph, "start")
    assume(len(start_neighbors) > 0)
    target_node = next(iter(start_neighbors))

    # Record visibility before the move
    visibility_before = copy.deepcopy(model.visible_nodes)

    # Execute the move via resolve_moves
    validated_move = ValidatedMove(
        model_id="model_a",
        target_node=target_node,
        valid=True,
    )
    resolve_moves([validated_move], game_state)

    # After move, get the model's current position (may differ if trap respawn)
    model_after = game_state.models["model_a"]
    final_position = model_after.current_node

    # The expected minimum visibility: previous visibility + new node + new node's neighbors
    # Note: if trap respawn happened, the model moves to a different position
    # and expand_visibility is called from there. We check that the final visible_nodes
    # is a superset of old visibility + final position + final position's neighbors.
    expected_minimum = visibility_before | {final_position} | _get_neighbors(graph, final_position)

    assert model_after.visible_nodes >= expected_minimum, (
        f"Visibility after move is not a superset of expected.\n"
        f"Missing: {expected_minimum - model_after.visible_nodes}\n"
        f"Final position: {final_position}\n"
        f"Visible after: {model_after.visible_nodes}\n"
        f"Expected minimum: {expected_minimum}"
    )


@settings(max_examples=100, deadline=5000)
@given(
    graph=arbitrary_connected_graph(),
    move_count=st.integers(min_value=1, max_value=3),
)
def test_property_13_movement_expands_visibility_multi_step(
    graph: Graph,
    move_count: int,
) -> None:
    """For any sequence of moves, each move SHALL expand visibility to be a superset
    of the previous visibility plus the new position's neighbors.

    **Validates: Requirements 3.2**
    """
    model = ModelState(
        model_id="model_b",
        strategy_name="test",
        current_node="start",
        score=0,
        visited_nodes={"start"},
        visible_nodes=set(),
        visible_edges=set(),
    )
    game_state = _make_game_state(graph, model)
    initialize_visibility("model_b", graph, game_state)

    current_pos = "start"
    for _ in range(move_count):
        neighbors = _get_neighbors(graph, current_pos)
        if not neighbors:
            break

        # Pick a non-trap neighbor to avoid respawn complexity
        safe_neighbors = [
            n for n in neighbors
            if graph.nodes[n].node_type != NodeType.TRAP
        ]
        if not safe_neighbors:
            break

        target = safe_neighbors[0]
        visibility_before = copy.deepcopy(game_state.models["model_b"].visible_nodes)

        validated_move = ValidatedMove(
            model_id="model_b",
            target_node=target,
            valid=True,
        )
        resolve_moves([validated_move], game_state)

        model_after = game_state.models["model_b"]
        final_pos = model_after.current_node

        expected_minimum = visibility_before | {final_pos} | _get_neighbors(graph, final_pos)
        assert model_after.visible_nodes >= expected_minimum

        current_pos = final_pos


# ---------------------------------------------------------------------------
# Property 14: ModelView accuracy
# **Validates: Requirements 3.5, 6.1**
# ---------------------------------------------------------------------------


@settings(max_examples=100, deadline=5000)
@given(
    graph=arbitrary_connected_graph(),
    initial_score=st.integers(min_value=0, max_value=500),
    turn_number=st.integers(min_value=1, max_value=50),
    has_checkpoint=st.booleans(),
)
def test_property_14_model_view_accuracy(
    graph: Graph,
    initial_score: int,
    turn_number: int,
    has_checkpoint: bool,
) -> None:
    """For any model at any point in the game, the ModelView provided to that model
    SHALL contain only nodes within the model's visibility set, and node type
    information SHALL only be included for visible nodes. The current_node,
    current_score, turn_number, and checkpoint status SHALL match the underlying
    game state.

    **Validates: Requirements 3.5, 6.1**
    """
    # Pick a checkpoint node if needed
    checkpoint_node = None
    if has_checkpoint:
        checkpoint_candidates = [
            nid for nid, n in graph.nodes.items()
            if n.node_type == NodeType.CHECKPOINT
        ]
        if checkpoint_candidates:
            checkpoint_node = checkpoint_candidates[0]
        else:
            has_checkpoint = False

    model = ModelState(
        model_id="model_view_test",
        strategy_name="test",
        current_node="start",
        score=initial_score,
        visited_nodes={"start"},
        visible_nodes=set(),
        visible_edges=set(),
        active_checkpoint=checkpoint_node,
    )
    config = GameConfig(
        graph_config=GraphConfig(map_reveal_depth=2),
        death_penalty=10,
        trap_respawn_penalty=5,
    )
    game_state = GameState(
        graph=graph,
        models={model.model_id: model},
        current_turn=turn_number,
        max_turns=100,
        config=config,
    )

    # Initialize visibility
    initialize_visibility(model.model_id, graph, game_state)

    # Build the ModelView
    model_view = _build_model_view(model.model_id, game_state)

    # --- Assertion 1: visible_nodes in ModelView only contains nodes within model's visibility set ---
    model_visibility_set = game_state.models[model.model_id].visible_nodes
    model_view_node_ids = set(model_view.visible_nodes.keys())
    assert model_view_node_ids <= model_visibility_set, (
        f"ModelView contains nodes outside visibility set.\n"
        f"Extra nodes: {model_view_node_ids - model_visibility_set}"
    )

    # --- Assertion 2: All visible nodes are included (completeness) ---
    # Every node in the model's visibility that exists in the graph should be in ModelView
    expected_visible = {nid for nid in model_visibility_set if nid in graph.nodes}
    assert model_view_node_ids == expected_visible, (
        f"ModelView is missing visible nodes.\n"
        f"Missing: {expected_visible - model_view_node_ids}"
    )

    # --- Assertion 3: Node type information is included for visible nodes ---
    for node_id, node in model_view.visible_nodes.items():
        assert node_id in model_visibility_set
        # The node type should match the actual graph node type
        assert node.node_type == graph.nodes[node_id].node_type

    # --- Assertion 4: current_node matches ---
    assert model_view.current_node == game_state.models[model.model_id].current_node

    # --- Assertion 5: current_score matches ---
    assert model_view.current_score == game_state.models[model.model_id].score

    # --- Assertion 6: turn_number matches ---
    assert model_view.turn_number == game_state.current_turn

    # --- Assertion 7: checkpoint status matches ---
    assert model_view.has_checkpoint == (game_state.models[model.model_id].active_checkpoint is not None)
    assert model_view.checkpoint_node == game_state.models[model.model_id].active_checkpoint


@settings(max_examples=100, deadline=5000)
@given(
    graph_data=arbitrary_linear_graph(),
    initial_score=st.integers(min_value=0, max_value=500),
)
def test_property_14_model_view_after_movement(
    graph_data: tuple[Graph, list[str]],
    initial_score: int,
) -> None:
    """After a model moves, the ModelView SHALL still only contain nodes
    within the model's (now expanded) visibility set and state SHALL match.

    **Validates: Requirements 3.5, 6.1**
    """
    graph, node_ids = graph_data

    model = ModelState(
        model_id="model_mv",
        strategy_name="test",
        current_node="start",
        score=initial_score,
        visited_nodes={"start"},
        visible_nodes=set(),
        visible_edges=set(),
    )
    game_state = _make_game_state(graph, model)
    initialize_visibility("model_mv", graph, game_state)

    # Move to a neighbor of start (pick one that's not a trap)
    start_neighbors = _get_neighbors(graph, "start")
    assume(len(start_neighbors) > 0)
    safe_targets = [
        n for n in start_neighbors
        if graph.nodes[n].node_type != NodeType.TRAP
    ]
    assume(len(safe_targets) > 0)
    target = safe_targets[0]

    validated_move = ValidatedMove(
        model_id="model_mv",
        target_node=target,
        valid=True,
    )
    resolve_moves([validated_move], game_state)

    # Build ModelView after move
    model_after = game_state.models["model_mv"]
    model_view = _build_model_view("model_mv", game_state)

    # ModelView nodes must be subset of model's visible_nodes
    model_view_node_ids = set(model_view.visible_nodes.keys())
    assert model_view_node_ids <= model_after.visible_nodes

    # ModelView must include all visible nodes
    expected_visible = {nid for nid in model_after.visible_nodes if nid in graph.nodes}
    assert model_view_node_ids == expected_visible

    # State fields must match
    assert model_view.current_node == model_after.current_node
    assert model_view.current_score == model_after.score
    assert model_view.turn_number == game_state.current_turn
    assert model_view.has_checkpoint == (model_after.active_checkpoint is not None)
    assert model_view.checkpoint_node == model_after.active_checkpoint
