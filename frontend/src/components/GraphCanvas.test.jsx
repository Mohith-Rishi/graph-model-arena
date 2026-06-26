import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { buildGraphData, getPlayersByNode, getMarkerOffsets, getAffectedNodes, GraphCanvas } from './GraphCanvas';
import * as GameContext from '../context/GameContext';

// Mock react-force-graph-2d since it requires canvas/WebGL
vi.mock('react-force-graph-2d', () => ({
  default: (props) => (
    <div data-testid="force-graph" data-nodes={JSON.stringify(props.graphData?.nodes)} />
  ),
}));

describe('buildGraphData', () => {
  it('returns empty arrays when graph is null', () => {
    const result = buildGraphData(null);
    expect(result).toEqual({ nodes: [], links: [] });
  });

  it('returns empty arrays when graph is undefined', () => {
    const result = buildGraphData(undefined);
    expect(result).toEqual({ nodes: [], links: [] });
  });

  it('converts nodes object to array with correct shape', () => {
    const graph = {
      nodes: {
        n1: { id: 'n1', node_type: 'START', point_value: 0 },
        n2: { id: 'n2', node_type: 'POINTS', point_value: 5 },
        n3: { id: 'n3', node_type: 'TRAP', point_value: 0 },
      },
      edges: [],
    };
    const result = buildGraphData(graph);

    expect(result.nodes).toHaveLength(3);
    expect(result.nodes).toContainEqual({ id: 'n1', nodeType: 'START', pointValue: 0 });
    expect(result.nodes).toContainEqual({ id: 'n2', nodeType: 'POINTS', pointValue: 5 });
    expect(result.nodes).toContainEqual({ id: 'n3', nodeType: 'TRAP', pointValue: 0 });
  });

  it('converts edges array to links with correct shape', () => {
    const graph = {
      nodes: {},
      edges: [
        { source: 'n1', target: 'n2', cost: 3, obstructed: false },
        { source: 'n2', target: 'n3', cost: 7, obstructed: true },
      ],
    };
    const result = buildGraphData(graph);

    expect(result.links).toHaveLength(2);
    expect(result.links[0]).toEqual({ source: 'n1', target: 'n2', cost: 3, obstructed: false });
    expect(result.links[1]).toEqual({ source: 'n2', target: 'n3', cost: 7, obstructed: true });
  });

  it('defaults obstructed to false when missing', () => {
    const graph = {
      nodes: {},
      edges: [{ source: 'a', target: 'b', cost: 1 }],
    };
    const result = buildGraphData(graph);
    expect(result.links[0].obstructed).toBe(false);
  });

  it('defaults pointValue to 0 when missing', () => {
    const graph = {
      nodes: { n1: { id: 'n1', node_type: 'NORMAL' } },
      edges: [],
    };
    const result = buildGraphData(graph);
    expect(result.nodes[0].pointValue).toBe(0);
  });
});

describe('getPlayersByNode', () => {
  it('returns empty object when snapshot is null', () => {
    expect(getPlayersByNode(null, [])).toEqual({});
  });

  it('returns empty object when playerPositions is missing', () => {
    expect(getPlayersByNode({}, ['model_a'])).toEqual({});
  });

  it('groups players by their current node', () => {
    const snapshot = {
      playerPositions: { model_a: 'n1', model_b: 'n2', model_c: 'n1' },
    };
    const playerOrder = ['model_a', 'model_b', 'model_c'];
    const result = getPlayersByNode(snapshot, playerOrder);

    expect(result['n1']).toHaveLength(2);
    expect(result['n2']).toHaveLength(1);
    expect(result['n1']).toContainEqual({ modelId: 'model_a', colorIndex: 0 });
    expect(result['n1']).toContainEqual({ modelId: 'model_c', colorIndex: 2 });
    expect(result['n2']).toContainEqual({ modelId: 'model_b', colorIndex: 1 });
  });

  it('assigns colorIndex 0 for unknown models not in playerOrder', () => {
    const snapshot = { playerPositions: { unknown_model: 'n1' } };
    const result = getPlayersByNode(snapshot, ['model_a', 'model_b']);

    expect(result['n1'][0].colorIndex).toBe(0);
  });
});

describe('getMarkerOffsets', () => {
  it('returns single offset above node for 1 player', () => {
    const offsets = getMarkerOffsets(1);
    expect(offsets).toHaveLength(1);
    expect(offsets[0].dx).toBe(0);
    expect(offsets[0].dy).toBeLessThan(0);
  });

  it('returns correct number of offsets for multiple players', () => {
    expect(getMarkerOffsets(2)).toHaveLength(2);
    expect(getMarkerOffsets(4)).toHaveLength(4);
    expect(getMarkerOffsets(8)).toHaveLength(8);
  });

  it('distributes offsets evenly (all same distance from center)', () => {
    const offsets = getMarkerOffsets(4);
    const distances = offsets.map((o) => Math.sqrt(o.dx * o.dx + o.dy * o.dy));
    const firstDistance = distances[0];
    distances.forEach((d) => {
      expect(d).toBeCloseTo(firstDistance, 5);
    });
  });

  it('offsets do not overlap for 2 players', () => {
    const offsets = getMarkerOffsets(2);
    const dist = Math.sqrt(
      Math.pow(offsets[0].dx - offsets[1].dx, 2) +
      Math.pow(offsets[0].dy - offsets[1].dy, 2)
    );
    expect(dist).toBeGreaterThan(0);
  });
});

describe('getAffectedNodes', () => {
  it('returns empty set when eventsThisTurn is null or empty', () => {
    expect(getAffectedNodes(null, {}, 'start')).toEqual(new Set());
    expect(getAffectedNodes([], {}, 'start')).toEqual(new Set());
  });

  it('returns target node for MOVE events', () => {
    const events = [
      { event_type: 'MOVE', model_id: 'model_a', details: { target_node: 'n3' } },
    ];
    const result = getAffectedNodes(events, {}, 'n1');
    expect(result.has('n3')).toBe(true);
    expect(result.size).toBe(1);
  });

  it('handles MOVE events with to_node fallback', () => {
    const events = [
      { event_type: 'MOVE', model_id: 'model_a', details: { to_node: 'n5' } },
    ];
    const result = getAffectedNodes(events, {}, 'n1');
    expect(result.has('n5')).toBe(true);
  });

  it('returns player current position for POINTS_COLLECTED events', () => {
    const events = [
      { event_type: 'POINTS_COLLECTED', model_id: 'model_a', details: { points_awarded: 10 } },
    ];
    const snapshot = { playerPositions: { model_a: 'n4' } };
    const result = getAffectedNodes(events, snapshot, 'n1');
    expect(result.has('n4')).toBe(true);
  });

  it('returns start node for TRAP_RESPAWN_START events', () => {
    const events = [
      { event_type: 'TRAP_RESPAWN_START', model_id: 'model_a', details: { death_penalty: 5 } },
    ];
    const result = getAffectedNodes(events, {}, 'start_node');
    expect(result.has('start_node')).toBe(true);
  });

  it('returns checkpoint node for TRAP_RESPAWN_CHECKPOINT events', () => {
    const events = [
      { event_type: 'TRAP_RESPAWN_CHECKPOINT', model_id: 'model_a', details: { checkpoint: 'cp1' } },
    ];
    const result = getAffectedNodes(events, {}, 'n1');
    expect(result.has('cp1')).toBe(true);
  });

  it('handles TRAP_RESPAWN_CHECKPOINT with checkpoint_node fallback', () => {
    const events = [
      { event_type: 'TRAP_RESPAWN_CHECKPOINT', model_id: 'model_a', details: { checkpoint_node: 'cp2' } },
    ];
    const result = getAffectedNodes(events, {}, 'n1');
    expect(result.has('cp2')).toBe(true);
  });

  it('collects multiple affected nodes from multiple events', () => {
    const events = [
      { event_type: 'MOVE', model_id: 'model_a', details: { target_node: 'n2' } },
      { event_type: 'MOVE', model_id: 'model_b', details: { target_node: 'n5' } },
    ];
    const result = getAffectedNodes(events, {}, 'n1');
    expect(result.has('n2')).toBe(true);
    expect(result.has('n5')).toBe(true);
    expect(result.size).toBe(2);
  });

  it('ignores unknown event types', () => {
    const events = [
      { event_type: 'UNKNOWN_EVENT', model_id: 'model_a', details: {} },
    ];
    const result = getAffectedNodes(events, {}, 'n1');
    expect(result.size).toBe(0);
  });

  it('deduplicates when multiple events affect same node', () => {
    const events = [
      { event_type: 'MOVE', model_id: 'model_a', details: { target_node: 'n3' } },
      { event_type: 'MOVE', model_id: 'model_b', details: { target_node: 'n3' } },
    ];
    const result = getAffectedNodes(events, {}, 'n1');
    expect(result.has('n3')).toBe(true);
    expect(result.size).toBe(1);
  });
});

describe('GraphCanvas component', () => {
  function renderWithContext(state) {
    vi.spyOn(GameContext, 'useGame').mockReturnValue({ state, dispatch: vi.fn() });
    return render(<GraphCanvas />);
  }

  it('shows empty message when no game is selected', () => {
    renderWithContext({ selectedGame: null, turnSnapshots: [], currentTurn: 0 });
    expect(screen.getByText('Select a game to view the graph.')).toBeInTheDocument();
  });

  it('renders ForceGraph2D when a game is selected', () => {
    const state = {
      selectedGame: {
        rankings: [{ model_id: 'model_a' }],
        full_state: {
          graph: {
            nodes: { n1: { id: 'n1', node_type: 'START', point_value: 0 } },
            edges: [],
            start_node: 'n1',
            end_node: 'n1',
          },
          models: { model_a: {} },
        },
      },
      turnSnapshots: [
        { turn: 0, playerPositions: { model_a: 'n1' }, playerScores: { model_a: 0 }, playerStatuses: { model_a: 'active' }, eventsThisTurn: [] },
      ],
      currentTurn: 0,
    };
    renderWithContext(state);

    expect(screen.getByTestId('force-graph')).toBeInTheDocument();
  });

  it('renders tooltip container', () => {
    const state = {
      selectedGame: {
        rankings: [{ model_id: 'model_a' }],
        full_state: {
          graph: {
            nodes: { n1: { id: 'n1', node_type: 'START', point_value: 0 } },
            edges: [],
            start_node: 'n1',
            end_node: 'n1',
          },
          models: { model_a: {} },
        },
      },
      turnSnapshots: [
        { turn: 0, playerPositions: { model_a: 'n1' }, playerScores: { model_a: 0 }, playerStatuses: { model_a: 'active' }, eventsThisTurn: [] },
      ],
      currentTurn: 0,
    };
    renderWithContext(state);

    expect(screen.getByRole('tooltip')).toBeInTheDocument();
  });

  it('passes correct graph data to ForceGraph2D', () => {
    const state = {
      selectedGame: {
        rankings: [],
        full_state: {
          graph: {
            nodes: {
              n1: { id: 'n1', node_type: 'START', point_value: 0 },
              n2: { id: 'n2', node_type: 'END', point_value: 0 },
            },
            edges: [{ source: 'n1', target: 'n2', cost: 5, obstructed: false }],
            start_node: 'n1',
            end_node: 'n2',
          },
          models: {},
        },
      },
      turnSnapshots: [
        { turn: 0, playerPositions: {}, playerScores: {}, playerStatuses: {}, eventsThisTurn: [] },
      ],
      currentTurn: 0,
    };
    renderWithContext(state);

    const graphEl = screen.getByTestId('force-graph');
    const nodes = JSON.parse(graphEl.getAttribute('data-nodes'));
    expect(nodes).toHaveLength(2);
    expect(nodes).toContainEqual({ id: 'n1', nodeType: 'START', pointValue: 0 });
    expect(nodes).toContainEqual({ id: 'n2', nodeType: 'END', pointValue: 0 });
  });
});
