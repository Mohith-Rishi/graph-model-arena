"""Graph Generator for Graph Model Arena.

Guarantees:
- Connected graph with exactly num_nodes nodes
- Exactly one START and one END node with a valid non-obstructed path
- A trap-free path from start to end exists
- Edge costs in [1, 10]
- Obstacles only on non-bridge edges (reachability preserved)
"""

from __future__ import annotations

import random
from collections import deque

from graph_model_arena.models import Edge, Graph, GraphConfig, Node, NodeType


class GraphGenerationError(Exception):
    """Raised when graph generation fails after max retries."""


class _RetryNeeded(Exception):
    """Internal signal to retry graph generation."""


def generate_graph(config: GraphConfig, *, max_retries: int = 10) -> Graph:
    """Generate a valid graph from *config*."""
    config.validate()
    for _ in range(max_retries):
        try:
            return _build_graph(config)
        except _RetryNeeded:
            continue
    raise GraphGenerationError(
        f"Failed to generate a valid graph after {max_retries} retries"
    )


def _build_graph(config: GraphConfig) -> Graph:
    n = config.num_nodes
    node_ids = [f"n{i}" for i in range(n)]

    adj: dict[str, set[str]] = {nid: set() for nid in node_ids}
    edge_set: set[tuple[str, str]] = set()

    # 1. Random spanning tree for guaranteed connectivity
    shuffled = list(node_ids)
    random.shuffle(shuffled)
    for i in range(1, n):
        a = shuffled[i]
        b = shuffled[random.randint(0, i - 1)]
        _add_undirected(adj, edge_set, a, b)

    # 2. Extra edges based on edge_density
    max_extra = n * (n - 1) // 2 - (n - 1)
    num_extra = int(config.edge_density * max_extra)
    all_pairs = [
        (node_ids[i], node_ids[j])
        for i in range(n)
        for j in range(i + 1, n)
        if (node_ids[i], node_ids[j]) not in edge_set
    ]
    random.shuffle(all_pairs)
    for a, b in all_pairs[:num_extra]:
        _add_undirected(adj, edge_set, a, b)

    # 3. Pick start/end to maximize distance
    start_id, end_id = _pick_start_end(node_ids, adj)

    # 4. Edge costs [1, 10]
    edge_costs: dict[tuple[str, str], int] = {}
    for a, b in edge_set:
        edge_costs[(a, b)] = random.randint(1, 10)

    # 5. Obstacles on non-bridge edges
    bridges = _find_bridges(node_ids, adj)
    non_bridge = [e for e in edge_set if e not in bridges]
    num_obstacles = int(config.obstacle_density * len(non_bridge))
    random.shuffle(non_bridge)
    obstructed: set[tuple[str, str]] = set()
    for e in non_bridge[:num_obstacles]:
        obstructed.add(e)
        if not _path_exists(start_id, end_id, adj, obstructed):
            obstructed.discard(e)

    # 6. Assign node types
    nodes = _assign_node_types(node_ids, start_id, end_id, config)

    # 7. Ensure trap-free path
    _ensure_trap_free_path(nodes, start_id, end_id, adj, obstructed)

    # 8. Assemble
    return _assemble_graph(nodes, edge_set, edge_costs, obstructed, adj, start_id, end_id)


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _add_undirected(
    adj: dict[str, set[str]],
    edge_set: set[tuple[str, str]],
    a: str,
    b: str,
) -> None:
    key = (min(a, b), max(a, b))
    if key not in edge_set:
        edge_set.add(key)
        adj[a].add(b)
        adj[b].add(a)


def _pick_start_end(
    node_ids: list[str], adj: dict[str, set[str]]
) -> tuple[str, str]:
    """Pick start/end nodes that maximize BFS distance."""
    origin = random.choice(node_ids)
    dist = _bfs_distances(origin, adj)
    start = max(dist, key=dist.get)  # type: ignore[arg-type]
    dist2 = _bfs_distances(start, adj)
    end = max(dist2, key=dist2.get)  # type: ignore[arg-type]
    if start == end:
        end = [nid for nid in node_ids if nid != start][0]
    return start, end


def _bfs_distances(source: str, adj: dict[str, set[str]]) -> dict[str, int]:
    dist: dict[str, int] = {source: 0}
    queue = deque([source])
    while queue:
        node = queue.popleft()
        for nb in adj[node]:
            if nb not in dist:
                dist[nb] = dist[node] + 1
                queue.append(nb)
    return dist


def _path_exists(
    start: str, end: str,
    adj: dict[str, set[str]],
    obstructed: set[tuple[str, str]],
) -> bool:
    """BFS reachability using non-obstructed edges."""
    visited: set[str] = {start}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == end:
            return True
        for nb in adj[node]:
            edge_key = (min(node, nb), max(node, nb))
            if nb not in visited and edge_key not in obstructed:
                visited.add(nb)
                queue.append(nb)
    return False


def _find_path(
    start: str, end: str,
    adj: dict[str, set[str]],
    obstructed: set[tuple[str, str]],
    avoid_types: set[NodeType] | None = None,
    nodes: dict[str, Node] | None = None,
) -> list[str] | None:
    """BFS shortest path, optionally avoiding certain node types."""
    parent: dict[str, str | None] = {start: None}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if node == end:
            path: list[str] = []
            cur: str | None = end
            while cur is not None:
                path.append(cur)
                cur = parent[cur]
            return path[::-1]
        for nb in adj[node]:
            if nb in parent:
                continue
            edge_key = (min(node, nb), max(node, nb))
            if edge_key in obstructed:
                continue
            if avoid_types and nodes and nb != end and nodes[nb].node_type in avoid_types:
                continue
            parent[nb] = node
            queue.append(nb)
    return None


# ---------------------------------------------------------------------------
# Bridge detection (iterative Tarjan)
# ---------------------------------------------------------------------------

def _find_bridges(
    node_ids: list[str], adj: dict[str, set[str]]
) -> set[tuple[str, str]]:
    disc: dict[str, int] = {}
    low: dict[str, int] = {}
    bridges: set[tuple[str, str]] = set()
    timer = 0

    for root in node_ids:
        if root in disc:
            continue
        stack: list[tuple[str, str | None, list[str]]] = [
            (root, None, list(adj[root]))
        ]
        disc[root] = low[root] = timer
        timer += 1

        while stack:
            node, parent, neighbors = stack[-1]
            if neighbors:
                nb = neighbors.pop()
                if nb == parent:
                    continue
                if nb in disc:
                    low[node] = min(low[node], disc[nb])
                else:
                    disc[nb] = low[nb] = timer
                    timer += 1
                    stack.append((nb, node, list(adj[nb])))
            else:
                stack.pop()
                if stack:
                    prev_node = stack[-1][0]
                    low[prev_node] = min(low[prev_node], low[node])
                    if low[node] > disc[prev_node]:
                        bridges.add((min(prev_node, node), max(prev_node, node)))
    return bridges


# ---------------------------------------------------------------------------
# Node type assignment
# ---------------------------------------------------------------------------

def _assign_node_types(
    node_ids: list[str],
    start_id: str,
    end_id: str,
    config: GraphConfig,
) -> dict[str, Node]:
    nodes: dict[str, Node] = {
        start_id: Node(id=start_id, node_type=NodeType.START),
        end_id: Node(id=end_id, node_type=NodeType.END),
    }

    type_weights: list[tuple[NodeType, float]] = [
        (NodeType.TRAP, config.trap_probability),
        (NodeType.CLUE, config.clue_probability),
        (NodeType.MAP, config.map_probability),
        (NodeType.CHECKPOINT, config.checkpoint_probability),
        (NodeType.POINTS, config.points_probability),
    ]
    special_total = sum(w for _, w in type_weights)
    normal_weight = max(0.0, 1.0 - special_total)
    types_list = [NodeType.NORMAL] + [t for t, _ in type_weights]
    weights_list = [normal_weight] + [w for _, w in type_weights]

    for nid in node_ids:
        if nid in (start_id, end_id):
            continue
        chosen = random.choices(types_list, weights=weights_list, k=1)[0]
        pv = 0
        if chosen == NodeType.POINTS:
            pv = random.randint(config.min_point_value, config.max_point_value)
        nodes[nid] = Node(id=nid, node_type=chosen, point_value=pv)

    return nodes


# ---------------------------------------------------------------------------
# Trap-free path guarantee
# ---------------------------------------------------------------------------

def _ensure_trap_free_path(
    nodes: dict[str, Node],
    start_id: str,
    end_id: str,
    adj: dict[str, set[str]],
    obstructed: set[tuple[str, str]],
) -> None:
    path = _find_path(
        start_id, end_id, adj, obstructed,
        avoid_types={NodeType.TRAP}, nodes=nodes,
    )
    if path is not None:
        return

    any_path = _find_path(start_id, end_id, adj, obstructed)
    if any_path is None:
        raise _RetryNeeded("No path from start to end")

    for nid in any_path:
        if nodes[nid].node_type == NodeType.TRAP:
            nodes[nid] = Node(id=nid, node_type=NodeType.NORMAL)


# ---------------------------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------------------------

def _assemble_graph(
    nodes: dict[str, Node],
    edge_set: set[tuple[str, str]],
    edge_costs: dict[tuple[str, str], int],
    obstructed: set[tuple[str, str]],
    adj: dict[str, set[str]],
    start_id: str,
    end_id: str,
) -> Graph:
    edges: list[Edge] = []
    adjacency: dict[str, list[tuple[str, Edge]]] = {nid: [] for nid in nodes}

    for a, b in edge_set:
        cost = edge_costs[(a, b)]
        obs = (a, b) in obstructed
        edge = Edge(source=a, target=b, cost=cost, obstructed=obs)
        edges.append(edge)
        adjacency[a].append((b, edge))
        adjacency[b].append((a, edge))

    return Graph(
        nodes=nodes,
        edges=edges,
        adjacency=adjacency,
        start_node=start_id,
        end_node=end_id,
    )
