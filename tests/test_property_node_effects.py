"""Property tests for Node Effects (Properties 6-10).

**Feature: graph-model-arena, Properties 6-10: Node Effects**
**Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 3.3, 3.4, 5.4**

Property 6: Trap respawn at start without checkpoint
Property 7: Trap respawn with checkpoint
Property 8: Clue node reveals exactly one neighbor's type
Property 9: Map node expands visibility by configured depth
Property 10: Checkpoint activation
"""

from __future__ import annotations

from collections import deque

from hypothesis import given, settings
from hypothesis import strategies as st

from graph_model_arena.models import (
    Edge,
    GameConfig,
    GameState,
    Graph,
    GraphConfig,
    ModelState,
    Node,
    NodeType,
)
from graph_model_arena.node_effects import process_node_effect


# ---------------------------------------------------------------------------
# Custom strategies for generating valid game states
# ---------------------------------------------------------------------------

_NODE_ID_ALPHABET = st.characters(whitelist_categories=("L", "N"))


@st.composite
def arbitrary_node_id(draw: st.DrawFn) -> str:
    """Generate a valid node ID."""
    return draw(st.text(min_size=1, max_size=8, alphabet=_NODE_ID_ALPHABET))


@st.composite
def arbitrary_death_penalty(draw: st.DrawFn) -> int:
    """Generate a valid death penalty value."""
    return draw(st.integers(min_value=1, max_value=50))


@st.composite
def arbitrary_trap_respawn_penalty(draw: st.DrawFn) -> int:
    """Generate a valid trap respawn penalty value."""
    return draw(st.integers(min_value=1, max_value=30))


@st.composite
def arbitrary_model_state(draw: st.DrawFn, current_node: str = "start") -> ModelState:
    """Generate a random ModelState at a given node."""
    model_id = draw(st.text(min_size=1, max_size=8, alphabet=_NODE_ID_ALPHABET))
    strategy_name = draw(st.sampled_from(["random_walker", "greedy_explorer", "shortest_path"]))
    score = draw(st.integers(min_value=0, max_value=1000))
    return ModelState(
        model_id=model_id,
        strategy_name=strategy_name,
        current_node=current_node,
        score=score,
        visited_nodes={current_node},
        visible_nodes={current_node},
        visible_edges=set(),
        trap_deaths=0,
    )


@st.composite
def arbitrary_graph_with_trap(draw: st.DrawFn) -> tuple[Graph, str, str]:
    """Generate a graph that has a start node, a trap node, and at least one edge.

    Returns (graph, start_node_id, trap_node_id).
    """
    start_id = "start"
    trap_id = "trap"
    # Add some extra normal nodes for realism
    num_extra = draw(st.integers(min_value=1, max_value=5))
    extra_ids = [f"n{i}" for i in range(num_extra)]

    nodes: dict[str, Node] = {
        start_id: Node(id=start_id, node_type=NodeType.START),
        trap_id: Node(id=trap_id, node_type=NodeType.TRAP),
    }
    for nid in extra_ids:
        nodes[nid] = Node(id=nid, node_type=NodeType.NORMAL)

    # End node
    end_id = "end"
    nodes[end_id] = Node(id=end_id, node_type=NodeType.END)

    # Connect start to trap and other nodes in a chain
    all_ids = [start_id] + extra_ids + [trap_id, end_id]
    edges: list[Edge] = []
    for i in range(len(all_ids) - 1):
        cost = draw(st.integers(min_value=1, max_value=10))
        edges.append(Edge(source=all_ids[i], target=all_ids[i + 1], cost=cost))

    adjacency: dict[str, list[tuple[str, Edge]]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, []).append((edge.target, edge))
        adjacency.setdefault(edge.target, []).append((edge.source, edge))

    graph = Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node=start_id,
        end_node=end_id,
    )
    return graph, start_id, trap_id


@st.composite
def arbitrary_graph_with_checkpoint_and_trap(draw: st.DrawFn) -> tuple[Graph, str, str, str]:
    """Generate a graph with start, checkpoint, and trap nodes.

    Returns (graph, start_id, checkpoint_id, trap_id).
    """
    start_id = "start"
    checkpoint_id = "checkpoint"
    trap_id = "trap"
    end_id = "end"

    nodes: dict[str, Node] = {
        start_id: Node(id=start_id, node_type=NodeType.START),
        checkpoint_id: Node(id=checkpoint_id, node_type=NodeType.CHECKPOINT),
        trap_id: Node(id=trap_id, node_type=NodeType.TRAP),
        end_id: Node(id=end_id, node_type=NodeType.END),
    }

    # Add extra nodes
    num_extra = draw(st.integers(min_value=0, max_value=4))
    extra_ids = [f"n{i}" for i in range(num_extra)]
    for nid in extra_ids:
        nodes[nid] = Node(id=nid, node_type=NodeType.NORMAL)

    # Build edges: start -> checkpoint -> trap, and some extras
    edges: list[Edge] = [
        Edge(source=start_id, target=checkpoint_id, cost=draw(st.integers(1, 10))),
        Edge(source=checkpoint_id, target=trap_id, cost=draw(st.integers(1, 10))),
        Edge(source=start_id, target=end_id, cost=draw(st.integers(1, 10))),
    ]
    # Connect extras
    prev = start_id
    for nid in extra_ids:
        edges.append(Edge(source=prev, target=nid, cost=draw(st.integers(1, 10))))
        prev = nid

    adjacency: dict[str, list[tuple[str, Edge]]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, []).append((edge.target, edge))
        adjacency.setdefault(edge.target, []).append((edge.source, edge))

    graph = Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node=start_id,
        end_node=end_id,
    )
    return graph, start_id, checkpoint_id, trap_id


@st.composite
def arbitrary_graph_with_clue(draw: st.DrawFn) -> tuple[Graph, str, str]:
    """Generate a graph with a clue node that has at least one neighbor.

    Returns (graph, start_id, clue_id).
    """
    start_id = "start"
    clue_id = "clue"
    end_id = "end"

    # Generate 2-5 neighbor nodes for the clue
    num_neighbors = draw(st.integers(min_value=1, max_value=5))
    neighbor_ids = [f"nb{i}" for i in range(num_neighbors)]
    neighbor_types = draw(
        st.lists(
            st.sampled_from([NodeType.NORMAL, NodeType.TRAP, NodeType.POINTS, NodeType.CHECKPOINT, NodeType.MAP]),
            min_size=num_neighbors,
            max_size=num_neighbors,
        )
    )

    nodes: dict[str, Node] = {
        start_id: Node(id=start_id, node_type=NodeType.START),
        clue_id: Node(id=clue_id, node_type=NodeType.CLUE),
        end_id: Node(id=end_id, node_type=NodeType.END),
    }
    for nid, ntype in zip(neighbor_ids, neighbor_types):
        pv = draw(st.integers(1, 10)) if ntype == NodeType.POINTS else 0
        nodes[nid] = Node(id=nid, node_type=ntype, point_value=pv)

    # Connect clue to all neighbors, and start to clue
    edges: list[Edge] = [
        Edge(source=start_id, target=clue_id, cost=draw(st.integers(1, 10))),
        Edge(source=start_id, target=end_id, cost=draw(st.integers(1, 10))),
    ]
    for nid in neighbor_ids:
        edges.append(Edge(source=clue_id, target=nid, cost=draw(st.integers(1, 10))))

    adjacency: dict[str, list[tuple[str, Edge]]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, []).append((edge.target, edge))
        adjacency.setdefault(edge.target, []).append((edge.source, edge))

    graph = Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node=start_id,
        end_node=end_id,
    )
    return graph, start_id, clue_id


@st.composite
def arbitrary_graph_with_map(draw: st.DrawFn) -> tuple[Graph, str, str, int]:
    """Generate a graph with a map node and sufficient depth for expansion.

    Returns (graph, start_id, map_id, map_reveal_depth).
    """
    start_id = "start"
    map_id = "map"
    end_id = "end"

    map_reveal_depth = draw(st.integers(min_value=1, max_value=3))

    # Generate a chain of nodes from map node outward to test depth expansion
    # We need at least map_reveal_depth levels of neighbors
    chain_length = map_reveal_depth + 2
    chain_ids = [f"c{i}" for i in range(chain_length)]

    nodes: dict[str, Node] = {
        start_id: Node(id=start_id, node_type=NodeType.START),
        map_id: Node(id=map_id, node_type=NodeType.MAP),
        end_id: Node(id=end_id, node_type=NodeType.END),
    }
    for cid in chain_ids:
        nodes[cid] = Node(id=cid, node_type=NodeType.NORMAL)

    # Edges: start -> map -> chain[0] -> chain[1] -> ... -> end
    edges: list[Edge] = [
        Edge(source=start_id, target=map_id, cost=draw(st.integers(1, 10))),
        Edge(source=map_id, target=chain_ids[0], cost=draw(st.integers(1, 10))),
        Edge(source=chain_ids[-1], target=end_id, cost=draw(st.integers(1, 10))),
    ]
    for i in range(len(chain_ids) - 1):
        edges.append(Edge(source=chain_ids[i], target=chain_ids[i + 1], cost=draw(st.integers(1, 10))))

    adjacency: dict[str, list[tuple[str, Edge]]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, []).append((edge.target, edge))
        adjacency.setdefault(edge.target, []).append((edge.source, edge))

    graph = Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node=start_id,
        end_node=end_id,
    )
    return graph, start_id, map_id, map_reveal_depth


@st.composite
def arbitrary_graph_with_checkpoint(draw: st.DrawFn) -> tuple[Graph, str, str]:
    """Generate a graph with a checkpoint node.

    Returns (graph, start_id, checkpoint_id).
    """
    start_id = "start"
    checkpoint_id = "checkpoint"
    end_id = "end"

    nodes: dict[str, Node] = {
        start_id: Node(id=start_id, node_type=NodeType.START),
        checkpoint_id: Node(id=checkpoint_id, node_type=NodeType.CHECKPOINT),
        end_id: Node(id=end_id, node_type=NodeType.END),
    }

    # Add extra nodes
    num_extra = draw(st.integers(min_value=0, max_value=4))
    extra_ids = [f"n{i}" for i in range(num_extra)]
    for nid in extra_ids:
        nodes[nid] = Node(id=nid, node_type=NodeType.NORMAL)

    # Edges
    edges: list[Edge] = [
        Edge(source=start_id, target=checkpoint_id, cost=draw(st.integers(1, 10))),
        Edge(source=checkpoint_id, target=end_id, cost=draw(st.integers(1, 10))),
    ]
    prev = start_id
    for nid in extra_ids:
        edges.append(Edge(source=prev, target=nid, cost=draw(st.integers(1, 10))))
        prev = nid

    adjacency: dict[str, list[tuple[str, Edge]]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, []).append((edge.target, edge))
        adjacency.setdefault(edge.target, []).append((edge.source, edge))

    graph = Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node=start_id,
        end_node=end_id,
    )
    return graph, start_id, checkpoint_id


def _make_game_state(
    graph: Graph,
    model_state: ModelState,
    death_penalty: int = 10,
    trap_respawn_penalty: int = 5,
    map_reveal_depth: int = 2,
) -> GameState:
    """Helper to build a GameState from a graph and a single model."""
    config = GameConfig(
        graph_config=GraphConfig(map_reveal_depth=map_reveal_depth),
        death_penalty=death_penalty,
        trap_respawn_penalty=trap_respawn_penalty,
    )
    return GameState(
        graph=graph,
        models={model_state.model_id: model_state},
        current_turn=1,
        max_turns=100,
        config=config,
    )


def _make_game_state_multi_model(
    graph: Graph,
    models: list[ModelState],
    death_penalty: int = 10,
    trap_respawn_penalty: int = 5,
    map_reveal_depth: int = 2,
) -> GameState:
    """Helper to build a GameState with multiple models."""
    config = GameConfig(
        graph_config=GraphConfig(map_reveal_depth=map_reveal_depth),
        death_penalty=death_penalty,
        trap_respawn_penalty=trap_respawn_penalty,
    )
    return GameState(
        graph=graph,
        models={m.model_id: m for m in models},
        current_turn=1,
        max_turns=100,
        config=config,
    )


def _bfs_nodes_within_depth(
    graph: Graph, center: str, depth: int
) -> set[str]:
    """BFS from center up to depth, returning all reachable node IDs."""
    visited: set[str] = set()
    queue: deque[tuple[str, int]] = deque()
    queue.append((center, 0))
    visited.add(center)

    while queue:
        node_id, dist = queue.popleft()
        if dist < depth:
            for neighbor_id, edge in graph.adjacency.get(node_id, []):
                if neighbor_id not in visited:
                    visited.add(neighbor_id)
                    queue.append((neighbor_id, dist + 1))
    return visited


def _bfs_edges_within_depth(
    graph: Graph, center: str, depth: int
) -> set[tuple[str, str]]:
    """BFS from center up to depth, returning all edge keys encountered."""
    visited_nodes: set[str] = set()
    edges: set[tuple[str, str]] = set()
    queue: deque[tuple[str, int]] = deque()
    queue.append((center, 0))
    visited_nodes.add(center)

    while queue:
        node_id, dist = queue.popleft()
        if dist < depth:
            for neighbor_id, edge in graph.adjacency.get(node_id, []):
                edge_key = (min(edge.source, edge.target), max(edge.source, edge.target))
                edges.add(edge_key)
                if neighbor_id not in visited_nodes:
                    visited_nodes.add(neighbor_id)
                    queue.append((neighbor_id, dist + 1))
    return edges


# ---------------------------------------------------------------------------
# Property 6: Trap respawn at start without checkpoint
# **Validates: Requirements 2.1, 5.4**
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=5000)
@given(
    graph_data=arbitrary_graph_with_trap(),
    score=st.integers(min_value=0, max_value=1000),
    death_penalty=arbitrary_death_penalty(),
)
def test_property_6_trap_respawn_at_start_without_checkpoint(
    graph_data: tuple[Graph, str, str],
    score: int,
    death_penalty: int,
) -> None:
    """For any model without an active checkpoint that enters a Trap_Node,
    the model SHALL remain alive, be repositioned at the Starting_Node,
    and the model's score SHALL be reduced by the configured death_penalty.
    """
    graph, start_id, trap_id = graph_data

    model = ModelState(
        model_id="model_test",
        strategy_name="test",
        current_node=trap_id,
        score=score,
        active_checkpoint=None,
        visited_nodes={start_id, trap_id},
        visible_nodes={start_id, trap_id},
        visible_edges=set(),
        trap_deaths=0,
    )

    game_state = _make_game_state(graph, model, death_penalty=death_penalty)
    trap_node = graph.nodes[trap_id]

    result = process_node_effect(model, trap_node, game_state)

    # Model remains alive (not finished)
    assert result.has_finished is False
    # Model repositioned at Starting_Node
    assert result.current_node == start_id
    # Score reduced by death_penalty
    assert result.score == score - death_penalty
    # Trap deaths incremented
    assert result.trap_deaths == 1


# ---------------------------------------------------------------------------
# Property 7: Trap respawn with checkpoint
# **Validates: Requirements 2.2**
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=5000)
@given(
    graph_data=arbitrary_graph_with_checkpoint_and_trap(),
    score=st.integers(min_value=0, max_value=1000),
    trap_respawn_penalty=arbitrary_trap_respawn_penalty(),
)
def test_property_7_trap_respawn_with_checkpoint(
    graph_data: tuple[Graph, str, str, str],
    score: int,
    trap_respawn_penalty: int,
) -> None:
    """For any model with an active checkpoint that enters a Trap_Node,
    the model SHALL be alive, positioned at the checkpoint node,
    and the model's score SHALL be reduced by the configured trap_respawn_penalty.
    """
    graph, start_id, checkpoint_id, trap_id = graph_data

    model = ModelState(
        model_id="model_test",
        strategy_name="test",
        current_node=trap_id,
        score=score,
        active_checkpoint=checkpoint_id,
        visited_nodes={start_id, checkpoint_id, trap_id},
        visible_nodes={start_id, checkpoint_id, trap_id},
        visible_edges=set(),
        trap_deaths=0,
    )

    game_state = _make_game_state(
        graph, model, trap_respawn_penalty=trap_respawn_penalty
    )
    trap_node = graph.nodes[trap_id]

    result = process_node_effect(model, trap_node, game_state)

    # Model remains alive
    assert result.has_finished is False
    # Model positioned at checkpoint
    assert result.current_node == checkpoint_id
    # Score reduced by trap_respawn_penalty
    assert result.score == score - trap_respawn_penalty
    # Trap deaths incremented
    assert result.trap_deaths == 1


# ---------------------------------------------------------------------------
# Property 8: Clue node reveals exactly one neighbor's type
# **Validates: Requirements 2.3, 3.4**
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=5000)
@given(graph_data=arbitrary_graph_with_clue())
def test_property_8_clue_reveals_exactly_one_neighbor(
    graph_data: tuple[Graph, str, str],
) -> None:
    """For any model entering a Clue_Node, exactly one neighboring node's type
    SHALL be added to that model's known information, and no other model's
    visibility SHALL change.
    """
    graph, start_id, clue_id = graph_data

    # Get clue node's neighbors from adjacency
    clue_neighbors = {nid for nid, _ in graph.adjacency.get(clue_id, [])}
    assert len(clue_neighbors) >= 1, "Clue node must have at least one neighbor"

    # Model starts with minimal visibility (only start and clue visible)
    model = ModelState(
        model_id="model_test",
        strategy_name="test",
        current_node=clue_id,
        score=50,
        active_checkpoint=None,
        visited_nodes={start_id, clue_id},
        visible_nodes={start_id, clue_id},
        visible_edges=set(),
    )

    # Second model to check isolation
    other_model = ModelState(
        model_id="model_other",
        strategy_name="test",
        current_node=start_id,
        score=30,
        active_checkpoint=None,
        visited_nodes={start_id},
        visible_nodes={start_id},
        visible_edges=set(),
    )

    game_state = _make_game_state_multi_model(graph, [model, other_model])
    other_visible_before = set(other_model.visible_nodes)

    clue_node = graph.nodes[clue_id]
    visible_before = set(model.visible_nodes)

    process_node_effect(model, clue_node, game_state)

    # Exactly one node was added to model's visible_nodes
    newly_revealed = model.visible_nodes - visible_before
    assert len(newly_revealed) == 1

    # The revealed node is a neighbor of the clue node
    revealed_node_id = next(iter(newly_revealed))
    assert revealed_node_id in clue_neighbors

    # Other model's visibility unchanged
    assert game_state.models["model_other"].visible_nodes == other_visible_before


# ---------------------------------------------------------------------------
# Property 9: Map node expands visibility by configured depth
# **Validates: Requirements 2.4, 3.3, 3.4**
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=5000)
@given(graph_data=arbitrary_graph_with_map())
def test_property_9_map_expands_visibility_by_depth(
    graph_data: tuple[Graph, str, str, int],
) -> None:
    """For any model entering a Map_Node, all nodes and edges within the
    configured map_reveal_depth from that Map_Node SHALL be added to that
    model's visibility, and no other model's visibility SHALL change.
    """
    graph, start_id, map_id, map_reveal_depth = graph_data

    # Model starts with minimal visibility
    model = ModelState(
        model_id="model_test",
        strategy_name="test",
        current_node=map_id,
        score=50,
        active_checkpoint=None,
        visited_nodes={start_id, map_id},
        visible_nodes={start_id, map_id},
        visible_edges=set(),
    )

    # Second model to check isolation
    other_model = ModelState(
        model_id="model_other",
        strategy_name="test",
        current_node=start_id,
        score=30,
        active_checkpoint=None,
        visited_nodes={start_id},
        visible_nodes={start_id},
        visible_edges=set(),
    )

    game_state = _make_game_state_multi_model(
        graph, [model, other_model], map_reveal_depth=map_reveal_depth
    )
    other_visible_before = set(other_model.visible_nodes)
    other_edges_before = set(other_model.visible_edges)

    map_node = graph.nodes[map_id]

    process_node_effect(model, map_node, game_state)

    # Compute expected BFS expansion from map_node
    expected_nodes = _bfs_nodes_within_depth(graph, map_id, map_reveal_depth)
    expected_edges = _bfs_edges_within_depth(graph, map_id, map_reveal_depth)

    # All nodes within depth should be visible
    assert expected_nodes.issubset(model.visible_nodes)

    # All edges within depth should be visible
    assert expected_edges.issubset(model.visible_edges)

    # Other model's visibility unchanged
    assert game_state.models["model_other"].visible_nodes == other_visible_before
    assert game_state.models["model_other"].visible_edges == other_edges_before


# ---------------------------------------------------------------------------
# Property 10: Checkpoint activation
# **Validates: Requirements 2.5**
# ---------------------------------------------------------------------------

@settings(max_examples=100, deadline=5000)
@given(graph_data=arbitrary_graph_with_checkpoint())
def test_property_10_checkpoint_activation(
    graph_data: tuple[Graph, str, str],
) -> None:
    """For any model entering a Checkpoint_Node, the model's active_checkpoint
    SHALL be set to that Checkpoint_Node's ID.
    """
    graph, start_id, checkpoint_id = graph_data

    model = ModelState(
        model_id="model_test",
        strategy_name="test",
        current_node=checkpoint_id,
        score=50,
        active_checkpoint=None,
        visited_nodes={start_id, checkpoint_id},
        visible_nodes={start_id, checkpoint_id},
        visible_edges=set(),
    )

    game_state = _make_game_state(graph, model)
    checkpoint_node = graph.nodes[checkpoint_id]

    result = process_node_effect(model, checkpoint_node, game_state)

    # Active checkpoint set to this checkpoint node's ID
    assert result.active_checkpoint == checkpoint_id


@settings(max_examples=100, deadline=5000)
@given(
    graph_data=arbitrary_graph_with_checkpoint(),
    previous_checkpoint=arbitrary_node_id(),
)
def test_property_10_checkpoint_overwrites_previous(
    graph_data: tuple[Graph, str, str],
    previous_checkpoint: str,
) -> None:
    """For any model with an existing checkpoint entering a new Checkpoint_Node,
    the model's active_checkpoint SHALL be updated to the new Checkpoint_Node's ID.
    """
    graph, start_id, checkpoint_id = graph_data

    model = ModelState(
        model_id="model_test",
        strategy_name="test",
        current_node=checkpoint_id,
        score=50,
        active_checkpoint=previous_checkpoint,
        visited_nodes={start_id, checkpoint_id},
        visible_nodes={start_id, checkpoint_id},
        visible_edges=set(),
    )

    game_state = _make_game_state(graph, model)
    checkpoint_node = graph.nodes[checkpoint_id]

    result = process_node_effect(model, checkpoint_node, game_state)

    # Active checkpoint updated to new checkpoint
    assert result.active_checkpoint == checkpoint_id
