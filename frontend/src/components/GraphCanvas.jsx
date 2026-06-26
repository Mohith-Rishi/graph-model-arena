import { useMemo, useCallback, useRef, useState, useEffect } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import { useGame } from '../context/GameContext';
import { NODE_COLORS, PLAYER_COLORS } from '../constants/colors';

const NODE_RADIUS = 8;
const PLAYER_MARKER_RADIUS = 5;
const PLAYER_MARKER_OFFSET = 12;
const HIGHLIGHT_DURATION_MS = 500;

/**
 * Extracts the set of node IDs affected by events at a given turn snapshot.
 * - MOVE: target node
 * - POINTS_COLLECTED: the player's current position (already moved)
 * - TRAP_RESPAWN_START: start node (player respawned there)
 * - TRAP_RESPAWN_CHECKPOINT: checkpoint node (player respawned there)
 */
export function getAffectedNodes(eventsThisTurn, snapshot, startNode) {
  const affected = new Set();
  if (!eventsThisTurn || eventsThisTurn.length === 0) return affected;

  for (const event of eventsThisTurn) {
    const { event_type: eventType, details, model_id: modelId } = event;
    switch (eventType) {
      case 'MOVE':
        if (details.target_node || details.to_node) {
          affected.add(details.target_node || details.to_node);
        }
        break;
      case 'POINTS_COLLECTED':
        // The player's position after events have been applied
        if (snapshot && snapshot.playerPositions && modelId) {
          affected.add(snapshot.playerPositions[modelId]);
        }
        break;
      case 'TRAP_RESPAWN_START':
        if (startNode) {
          affected.add(startNode);
        }
        break;
      case 'TRAP_RESPAWN_CHECKPOINT':
        if (details.checkpoint || details.checkpoint_node) {
          affected.add(details.checkpoint || details.checkpoint_node);
        }
        break;
      default:
        break;
    }
  }
  return affected;
}

/**
 * Converts the backend graph data and current turn snapshot into
 * the format expected by react-force-graph-2d.
 */
export function buildGraphData(graph) {
  if (!graph) return { nodes: [], links: [] };

  const nodes = Object.values(graph.nodes || {}).map((node) => ({
    id: node.id,
    nodeType: node.node_type,
    pointValue: node.point_value || 0,
  }));

  const links = (graph.edges || []).map((edge) => ({
    source: edge.source,
    target: edge.target,
    cost: edge.cost,
    obstructed: edge.obstructed || false,
  }));

  return { nodes, links };
}

/**
 * Computes player positions on the current turn, returning a map of
 * nodeId -> array of { modelId, colorIndex } for rendering markers.
 */
export function getPlayersByNode(snapshot, playerOrder) {
  if (!snapshot || !snapshot.playerPositions) return {};

  const byNode = {};
  for (const modelId of Object.keys(snapshot.playerPositions)) {
    const nodeId = snapshot.playerPositions[modelId];
    if (!byNode[nodeId]) {
      byNode[nodeId] = [];
    }
    const colorIndex = playerOrder.indexOf(modelId);
    byNode[nodeId].push({ modelId, colorIndex: colorIndex >= 0 ? colorIndex : 0 });
  }
  return byNode;
}

/**
 * Returns offset positions for multiple player markers around a node center.
 * Distributes markers evenly in a circle around the node.
 */
export function getMarkerOffsets(count) {
  if (count === 1) return [{ dx: 0, dy: -PLAYER_MARKER_OFFSET }];
  const offsets = [];
  for (let i = 0; i < count; i++) {
    const angle = (2 * Math.PI * i) / count - Math.PI / 2;
    offsets.push({
      dx: Math.cos(angle) * PLAYER_MARKER_OFFSET,
      dy: Math.sin(angle) * PLAYER_MARKER_OFFSET,
    });
  }
  return offsets;
}

export function GraphCanvas() {
  const { state } = useGame();
  const { selectedGame, turnSnapshots, currentTurn } = state;
  const tooltipRef = useRef(null);
  const [highlightedNodes, setHighlightedNodes] = useState(new Set());

  const graph = selectedGame?.full_state?.graph;
  const snapshot = turnSnapshots[currentTurn];
  const startNode = graph?.start_node;

  // Highlight affected nodes when turn changes
  useEffect(() => {
    if (!snapshot || !snapshot.eventsThisTurn || snapshot.eventsThisTurn.length === 0) {
      setHighlightedNodes(new Set());
      return;
    }

    const affected = getAffectedNodes(snapshot.eventsThisTurn, snapshot, startNode);
    if (affected.size === 0) {
      setHighlightedNodes(new Set());
      return;
    }

    setHighlightedNodes(affected);

    const timer = setTimeout(() => {
      setHighlightedNodes(new Set());
    }, HIGHLIGHT_DURATION_MS);

    return () => clearTimeout(timer);
  }, [currentTurn, snapshot, startNode]);

  // Determine stable player ordering for color assignment
  const playerOrder = useMemo(() => {
    if (!selectedGame) return [];
    if (selectedGame.rankings && selectedGame.rankings.length > 0) {
      return selectedGame.rankings.map((r) => r.model_id);
    }
    if (selectedGame.full_state?.models) {
      return Object.keys(selectedGame.full_state.models);
    }
    return [];
  }, [selectedGame]);

  // Build graph data for react-force-graph-2d
  const graphData = useMemo(() => buildGraphData(graph), [graph]);

  // Compute player positions by node
  const playersByNode = useMemo(
    () => getPlayersByNode(snapshot, playerOrder),
    [snapshot, playerOrder]
  );

  // Custom node rendering
  const nodeCanvasObject = useCallback(
    (node, ctx, globalScale) => {
      const color = NODE_COLORS[node.nodeType] || NODE_COLORS.NORMAL;
      const radius = NODE_RADIUS;

      // Draw highlight ring if node is affected by current turn events
      if (highlightedNodes.has(node.id)) {
        const highlightRadius = radius + 5;
        ctx.beginPath();
        ctx.arc(node.x, node.y, highlightRadius, 0, 2 * Math.PI);
        ctx.fillStyle = 'rgba(255, 235, 59, 0.4)';
        ctx.fill();
        ctx.strokeStyle = 'rgba(255, 193, 7, 0.8)';
        ctx.lineWidth = 2;
        ctx.stroke();
      }

      // Draw node circle
      ctx.beginPath();
      ctx.arc(node.x, node.y, radius, 0, 2 * Math.PI);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.strokeStyle = '#333';
      ctx.lineWidth = 1;
      ctx.stroke();

      // Draw point value inside POINTS nodes
      if (node.pointValue > 0) {
        ctx.font = `${Math.max(3, 10 / globalScale)}px Sans-Serif`;
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = '#000';
        ctx.fillText(String(node.pointValue), node.x, node.y);
      }

      // Draw player markers at this node
      const players = playersByNode[node.id];
      if (players && players.length > 0) {
        const offsets = getMarkerOffsets(players.length);
        players.forEach((player, i) => {
          const offset = offsets[i];
          const px = node.x + offset.dx;
          const py = node.y + offset.dy;
          const playerColor = PLAYER_COLORS[player.colorIndex % PLAYER_COLORS.length];

          ctx.beginPath();
          ctx.arc(px, py, PLAYER_MARKER_RADIUS, 0, 2 * Math.PI);
          ctx.fillStyle = playerColor;
          ctx.fill();
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 1;
          ctx.stroke();
        });
      }
    },
    [playersByNode, highlightedNodes]
  );

  // Custom link rendering with dashed style for obstructed edges
  const linkCanvasObject = useCallback((link, ctx, globalScale) => {
    const start = link.source;
    const end = link.target;

    if (!start || !end || typeof start.x === 'undefined') return;

    ctx.beginPath();
    if (link.obstructed) {
      ctx.setLineDash([4, 4]);
    } else {
      ctx.setLineDash([]);
    }
    ctx.moveTo(start.x, start.y);
    ctx.lineTo(end.x, end.y);
    ctx.strokeStyle = link.obstructed ? '#999' : '#666';
    ctx.lineWidth = 1.5;
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw cost label at midpoint
    const midX = (start.x + end.x) / 2;
    const midY = (start.y + end.y) / 2;
    ctx.font = `${Math.max(3, 8 / globalScale)}px Sans-Serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillStyle = '#444';
    ctx.fillText(String(link.cost), midX, midY);
  }, []);

  // Tooltip on hover
  const handleNodeHover = useCallback((node) => {
    if (tooltipRef.current) {
      if (node) {
        tooltipRef.current.textContent = `Node: ${node.id} (Type: ${node.nodeType})`;
        tooltipRef.current.style.display = 'block';
      } else {
        tooltipRef.current.style.display = 'none';
      }
    }
  }, []);

  if (!selectedGame || !graph) {
    return <div className="graph-canvas-empty">Select a game to view the graph.</div>;
  }

  return (
    <div className="graph-canvas" style={{ position: 'relative', width: '100%', height: '100%' }}>
      <div
        ref={tooltipRef}
        className="node-tooltip"
        role="tooltip"
        style={{
          display: 'none',
          position: 'absolute',
          top: 8,
          left: 8,
          background: 'rgba(0,0,0,0.8)',
          color: '#fff',
          padding: '4px 8px',
          borderRadius: '4px',
          fontSize: '12px',
          pointerEvents: 'none',
          zIndex: 10,
        }}
      />
      <ForceGraph2D
        graphData={graphData}
        nodeCanvasObject={nodeCanvasObject}
        nodeCanvasObjectMode={() => 'replace'}
        linkCanvasObject={linkCanvasObject}
        linkCanvasObjectMode={() => 'replace'}
        onNodeHover={handleNodeHover}
        nodeId="id"
        linkSource="source"
        linkTarget="target"
        width={800}
        height={600}
      />
    </div>
  );
}
