import { describe, it, expect } from 'vitest';
import { computeTurnSnapshots } from './computeTurnSnapshots';

/**
 * Helper to build a minimal valid fullState for testing.
 */
function makeFullState(overrides = {}) {
  return {
    graph: {
      nodes: { n1: { id: 'n1', node_type: 'START' }, n2: { id: 'n2', node_type: 'NORMAL' }, n3: { id: 'n3', node_type: 'END' } },
      edges: [{ source: 'n1', target: 'n2', cost: 1 }, { source: 'n2', target: 'n3', cost: 1 }],
      start_node: 'n1',
      end_node: 'n3',
    },
    models: {
      model_a: { current_node: 'n2', score: 5 },
      model_b: { current_node: 'n1', score: 0 },
    },
    event_log: [],
    current_turn: 0,
    max_turns: 50,
    ...overrides,
  };
}

describe('computeTurnSnapshots', () => {
  describe('initial state (turn 0)', () => {
    it('returns a single snapshot at turn 0 when there are no events', () => {
      const state = makeFullState();
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots).toHaveLength(1);
      expect(snapshots[0].turn).toBe(0);
    });

    it('initializes all players at start_node with score 0 and active status', () => {
      const state = makeFullState();
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[0].playerPositions).toEqual({ model_a: 'n1', model_b: 'n1' });
      expect(snapshots[0].playerScores).toEqual({ model_a: 0, model_b: 0 });
      expect(snapshots[0].playerStatuses).toEqual({ model_a: 'active', model_b: 'active' });
    });

    it('has no events at turn 0', () => {
      const state = makeFullState();
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[0].eventsThisTurn).toEqual([]);
    });
  });

  describe('MOVE events', () => {
    it('updates player position using details.target_node', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_a', event_type: 'MOVE', details: { target_node: 'n2' } },
        ],
        current_turn: 1,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[1].playerPositions.model_a).toBe('n2');
      expect(snapshots[1].playerPositions.model_b).toBe('n1'); // unchanged
    });

    it('updates player position using details.to_node as fallback', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_b', event_type: 'MOVE', details: { to_node: 'n3' } },
        ],
        current_turn: 1,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[1].playerPositions.model_b).toBe('n3');
    });
  });

  describe('POINTS_COLLECTED events', () => {
    it('increments score using details.points_awarded', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_a', event_type: 'POINTS_COLLECTED', details: { points_awarded: 10 } },
        ],
        current_turn: 1,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[1].playerScores.model_a).toBe(10);
      expect(snapshots[1].playerScores.model_b).toBe(0);
    });

    it('increments score using details.points as fallback', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_a', event_type: 'POINTS_COLLECTED', details: { points: 7 } },
        ],
        current_turn: 1,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[1].playerScores.model_a).toBe(7);
    });

    it('accumulates points across turns', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_a', event_type: 'POINTS_COLLECTED', details: { points_awarded: 5 } },
          { turn: 2, model_id: 'model_a', event_type: 'POINTS_COLLECTED', details: { points_awarded: 3 } },
        ],
        current_turn: 2,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[1].playerScores.model_a).toBe(5);
      expect(snapshots[2].playerScores.model_a).toBe(8);
    });
  });

  describe('TRAP_RESPAWN_START events', () => {
    it('moves player to start_node and decrements score by death_penalty', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_a', event_type: 'MOVE', details: { target_node: 'n2' } },
          { turn: 2, model_id: 'model_a', event_type: 'TRAP_RESPAWN_START', details: { death_penalty: 5 } },
        ],
        current_turn: 2,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[2].playerPositions.model_a).toBe('n1');
      expect(snapshots[2].playerScores.model_a).toBe(-5);
    });

    it('uses details.penalty as fallback', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_a', event_type: 'TRAP_RESPAWN_START', details: { penalty: 3 } },
        ],
        current_turn: 1,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[1].playerPositions.model_a).toBe('n1');
      expect(snapshots[1].playerScores.model_a).toBe(-3);
    });
  });

  describe('TRAP_RESPAWN_CHECKPOINT events', () => {
    it('moves player to checkpoint and decrements score by trap_respawn_penalty', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_a', event_type: 'MOVE', details: { target_node: 'n2' } },
          { turn: 2, model_id: 'model_a', event_type: 'TRAP_RESPAWN_CHECKPOINT', details: { checkpoint: 'n2', trap_respawn_penalty: 2 } },
        ],
        current_turn: 2,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[2].playerPositions.model_a).toBe('n2');
      expect(snapshots[2].playerScores.model_a).toBe(-2);
    });

    it('uses details.checkpoint_node and details.penalty as fallbacks', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_b', event_type: 'TRAP_RESPAWN_CHECKPOINT', details: { checkpoint_node: 'n2', penalty: 4 } },
        ],
        current_turn: 1,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[1].playerPositions.model_b).toBe('n2');
      expect(snapshots[1].playerScores.model_b).toBe(-4);
    });
  });

  describe('INVALID_MOVE events', () => {
    it('decrements score by invalid_move_penalty', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_a', event_type: 'INVALID_MOVE', details: { invalid_move_penalty: 1 } },
        ],
        current_turn: 1,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[1].playerScores.model_a).toBe(-1);
      expect(snapshots[1].playerPositions.model_a).toBe('n1'); // position unchanged
    });

    it('uses details.penalty as fallback', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_b', event_type: 'INVALID_MOVE', details: { penalty: 2 } },
        ],
        current_turn: 1,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[1].playerScores.model_b).toBe(-2);
    });
  });

  describe('GAME_FINISHED events', () => {
    it('marks player status as finished', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_a', event_type: 'GAME_FINISHED', details: {} },
        ],
        current_turn: 1,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[1].playerStatuses.model_a).toBe('finished');
      expect(snapshots[1].playerStatuses.model_b).toBe('active');
    });

    it('finished status persists across subsequent turns', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_a', event_type: 'GAME_FINISHED', details: {} },
          { turn: 2, model_id: 'model_b', event_type: 'MOVE', details: { target_node: 'n2' } },
        ],
        current_turn: 2,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[2].playerStatuses.model_a).toBe('finished');
      expect(snapshots[2].playerStatuses.model_b).toBe('active');
    });
  });

  describe('snapshot structure and turn count', () => {
    it('produces totalTurns + 1 snapshots (turn 0 through max event turn)', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_a', event_type: 'MOVE', details: { target_node: 'n2' } },
          { turn: 3, model_id: 'model_b', event_type: 'MOVE', details: { target_node: 'n2' } },
        ],
        current_turn: 3,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots).toHaveLength(4); // turns 0, 1, 2, 3
    });

    it('uses current_turn when it exceeds max event turn', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_a', event_type: 'MOVE', details: { target_node: 'n2' } },
        ],
        current_turn: 5,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots).toHaveLength(6); // turns 0 through 5
    });

    it('includes eventsThisTurn with the correct events', () => {
      const moveEvent = { turn: 1, model_id: 'model_a', event_type: 'MOVE', details: { target_node: 'n2' } };
      const pointsEvent = { turn: 1, model_id: 'model_b', event_type: 'POINTS_COLLECTED', details: { points_awarded: 5 } };
      const state = makeFullState({
        event_log: [moveEvent, pointsEvent],
        current_turn: 1,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[1].eventsThisTurn).toEqual([moveEvent, pointsEvent]);
      expect(snapshots[0].eventsThisTurn).toEqual([]);
    });

    it('turns without events still get a snapshot with carried-over state', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'model_a', event_type: 'MOVE', details: { target_node: 'n2' } },
          { turn: 3, model_id: 'model_a', event_type: 'MOVE', details: { target_node: 'n3' } },
        ],
        current_turn: 3,
      });
      const snapshots = computeTurnSnapshots(state);

      // Turn 2 has no events but carries state from turn 1
      expect(snapshots[2].playerPositions.model_a).toBe('n2');
      expect(snapshots[2].eventsThisTurn).toEqual([]);
    });
  });

  describe('complex multi-event scenario', () => {
    it('correctly applies a sequence of mixed events', () => {
      const state = makeFullState({
        graph: {
          nodes: { n1: {}, n2: {}, n3: {}, n4: {} },
          edges: [],
          start_node: 'n1',
          end_node: 'n4',
        },
        models: { alice: {}, bob: {} },
        event_log: [
          { turn: 1, model_id: 'alice', event_type: 'MOVE', details: { target_node: 'n2' } },
          { turn: 1, model_id: 'bob', event_type: 'MOVE', details: { target_node: 'n3' } },
          { turn: 2, model_id: 'alice', event_type: 'POINTS_COLLECTED', details: { points_awarded: 10 } },
          { turn: 2, model_id: 'bob', event_type: 'TRAP_RESPAWN_START', details: { death_penalty: 3 } },
          { turn: 3, model_id: 'alice', event_type: 'MOVE', details: { target_node: 'n4' } },
          { turn: 3, model_id: 'alice', event_type: 'GAME_FINISHED', details: {} },
          { turn: 3, model_id: 'bob', event_type: 'INVALID_MOVE', details: { invalid_move_penalty: 1 } },
        ],
        current_turn: 3,
      });
      const snapshots = computeTurnSnapshots(state);

      // Turn 0 - initial state
      expect(snapshots[0].playerPositions).toEqual({ alice: 'n1', bob: 'n1' });
      expect(snapshots[0].playerScores).toEqual({ alice: 0, bob: 0 });

      // Turn 1 - both move
      expect(snapshots[1].playerPositions).toEqual({ alice: 'n2', bob: 'n3' });
      expect(snapshots[1].playerScores).toEqual({ alice: 0, bob: 0 });

      // Turn 2 - alice gets points, bob hits trap
      expect(snapshots[2].playerPositions).toEqual({ alice: 'n2', bob: 'n1' });
      expect(snapshots[2].playerScores).toEqual({ alice: 10, bob: -3 });

      // Turn 3 - alice finishes, bob invalid move
      expect(snapshots[3].playerPositions).toEqual({ alice: 'n4', bob: 'n1' });
      expect(snapshots[3].playerScores).toEqual({ alice: 10, bob: -4 });
      expect(snapshots[3].playerStatuses).toEqual({ alice: 'finished', bob: 'active' });
    });
  });

  describe('edge cases', () => {
    it('handles a single player game', () => {
      const state = makeFullState({
        models: { solo: {} },
        event_log: [
          { turn: 1, model_id: 'solo', event_type: 'MOVE', details: { target_node: 'n2' } },
        ],
        current_turn: 1,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[0].playerPositions).toEqual({ solo: 'n1' });
      expect(snapshots[1].playerPositions).toEqual({ solo: 'n2' });
    });

    it('skips events for unknown models without crashing', () => {
      const state = makeFullState({
        event_log: [
          { turn: 1, model_id: 'unknown_model', event_type: 'MOVE', details: { target_node: 'n2' } },
          { turn: 1, model_id: 'model_a', event_type: 'MOVE', details: { target_node: 'n2' } },
        ],
        current_turn: 1,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots[1].playerPositions.model_a).toBe('n2');
      expect(snapshots[1].playerPositions).not.toHaveProperty('unknown_model');
    });

    it('handles empty models object', () => {
      const state = makeFullState({
        models: {},
        event_log: [],
        current_turn: 0,
      });
      const snapshots = computeTurnSnapshots(state);

      expect(snapshots).toHaveLength(1);
      expect(snapshots[0].playerPositions).toEqual({});
      expect(snapshots[0].playerScores).toEqual({});
      expect(snapshots[0].playerStatuses).toEqual({});
    });
  });
});
