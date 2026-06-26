import { describe, it, expect } from 'vitest';
import { parseGameData } from './parseGameData';

/**
 * Helper to build a valid game object for testing.
 */
function makeValidGame(overrides = {}) {
  return {
    game_id: 'game-001',
    timestamp: '2024-01-15T10:30:00Z',
    config: {},
    rankings: [],
    graph_stats: {},
    total_turns: 10,
    full_state: {
      graph: { nodes: {}, edges: [], start_node: 'n1', end_node: 'n5' },
      models: { model_a: {} },
      event_log: [],
      current_turn: 10,
      max_turns: 50,
    },
    ...overrides,
  };
}

describe('parseGameData', () => {
  describe('invalid JSON', () => {
    it('returns error for completely invalid JSON', () => {
      const result = parseGameData('not json at all');
      expect(result).toEqual({
        success: false,
        error: 'Invalid JSON file. Please upload a valid game_results.json',
      });
    });

    it('returns error for partial JSON', () => {
      const result = parseGameData('{"incomplete":');
      expect(result).toEqual({
        success: false,
        error: 'Invalid JSON file. Please upload a valid game_results.json',
      });
    });
  });

  describe('not an array', () => {
    it('returns error for a plain object', () => {
      const result = parseGameData(JSON.stringify({ game_id: 'test' }));
      expect(result).toEqual({
        success: false,
        error: 'Expected an array of game results',
      });
    });

    it('returns error for a string value', () => {
      const result = parseGameData(JSON.stringify('hello'));
      expect(result).toEqual({
        success: false,
        error: 'Expected an array of game results',
      });
    });

    it('returns error for a number', () => {
      const result = parseGameData(JSON.stringify(42));
      expect(result).toEqual({
        success: false,
        error: 'Expected an array of game results',
      });
    });
  });

  describe('empty array', () => {
    it('returns success with empty games array', () => {
      const result = parseGameData(JSON.stringify([]));
      expect(result).toEqual({ success: true, games: [] });
    });
  });

  describe('missing required fields', () => {
    it('returns error when game_id is missing', () => {
      const game = makeValidGame();
      delete game.game_id;
      const result = parseGameData(JSON.stringify([game]));
      expect(result).toEqual({
        success: false,
        error: 'Game data incomplete — game_id and timestamp are required',
      });
    });

    it('returns error when timestamp is missing', () => {
      const game = makeValidGame();
      delete game.timestamp;
      const result = parseGameData(JSON.stringify([game]));
      expect(result).toEqual({
        success: false,
        error: 'Game data incomplete — game_id and timestamp are required',
      });
    });

    it('returns error when full_state is missing', () => {
      const game = makeValidGame();
      delete game.full_state;
      const result = parseGameData(JSON.stringify([game]));
      expect(result).toEqual({
        success: false,
        error: 'Game data incomplete — full_state is required for visualization',
      });
    });

    it('returns error when full_state.graph is missing', () => {
      const game = makeValidGame();
      delete game.full_state.graph;
      const result = parseGameData(JSON.stringify([game]));
      expect(result).toEqual({
        success: false,
        error: 'Game data incomplete — full_state must contain graph, models, and event_log',
      });
    });

    it('returns error when full_state.models is missing', () => {
      const game = makeValidGame();
      delete game.full_state.models;
      const result = parseGameData(JSON.stringify([game]));
      expect(result).toEqual({
        success: false,
        error: 'Game data incomplete — full_state must contain graph, models, and event_log',
      });
    });

    it('returns error when full_state.event_log is missing', () => {
      const game = makeValidGame();
      delete game.full_state.event_log;
      const result = parseGameData(JSON.stringify([game]));
      expect(result).toEqual({
        success: false,
        error: 'Game data incomplete — full_state must contain graph, models, and event_log',
      });
    });
  });

  describe('valid input and sorting', () => {
    it('returns success for a single valid game', () => {
      const game = makeValidGame();
      const result = parseGameData(JSON.stringify([game]));
      expect(result.success).toBe(true);
      expect(result.games).toHaveLength(1);
      expect(result.games[0].game_id).toBe('game-001');
    });

    it('sorts games by timestamp descending (most recent first)', () => {
      const games = [
        makeValidGame({ game_id: 'oldest', timestamp: '2024-01-01T00:00:00Z' }),
        makeValidGame({ game_id: 'newest', timestamp: '2024-03-01T00:00:00Z' }),
        makeValidGame({ game_id: 'middle', timestamp: '2024-02-01T00:00:00Z' }),
      ];
      const result = parseGameData(JSON.stringify(games));
      expect(result.success).toBe(true);
      expect(result.games[0].game_id).toBe('newest');
      expect(result.games[1].game_id).toBe('middle');
      expect(result.games[2].game_id).toBe('oldest');
    });

    it('does not mutate the original order (returns a new array)', () => {
      const games = [
        makeValidGame({ game_id: 'a', timestamp: '2024-01-01T00:00:00Z' }),
        makeValidGame({ game_id: 'b', timestamp: '2024-02-01T00:00:00Z' }),
      ];
      const json = JSON.stringify(games);
      const result = parseGameData(json);
      // The original JSON still has 'a' first
      expect(JSON.parse(json)[0].game_id).toBe('a');
      // The result has 'b' first (more recent)
      expect(result.games[0].game_id).toBe('b');
    });

    it('validates all games in the array (fails on second invalid game)', () => {
      const games = [
        makeValidGame({ game_id: 'valid-1', timestamp: '2024-01-01T00:00:00Z' }),
        makeValidGame({ game_id: 'valid-2', timestamp: '2024-02-01T00:00:00Z' }),
      ];
      delete games[1].full_state;
      const result = parseGameData(JSON.stringify(games));
      expect(result.success).toBe(false);
      expect(result.error).toContain('full_state is required');
    });
  });
});
