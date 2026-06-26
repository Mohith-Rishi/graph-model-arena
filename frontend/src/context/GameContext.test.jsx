import { describe, it, expect } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { GameProvider, useGame } from './GameContext';

function createMockGame(overrides = {}) {
  return {
    game_id: 'test-game-1',
    timestamp: '2024-01-01T00:00:00Z',
    full_state: {
      graph: {
        start_node: 'node_0',
        end_node: 'node_5',
        nodes: { node_0: { id: 'node_0', node_type: 'START' } },
        edges: [],
      },
      models: {
        model_a: { current_node: 'node_0', score: 0 },
        model_b: { current_node: 'node_0', score: 0 },
      },
      event_log: [
        { turn: 1, model_id: 'model_a', event_type: 'MOVE', details: { target_node: 'node_1' } },
        { turn: 1, model_id: 'model_b', event_type: 'MOVE', details: { target_node: 'node_2' } },
        { turn: 2, model_id: 'model_a', event_type: 'POINTS_COLLECTED', details: { points_awarded: 10 } },
      ],
      current_turn: 2,
      max_turns: 10,
    },
    ...overrides,
  };
}

function renderUseGame() {
  return renderHook(() => useGame(), {
    wrapper: GameProvider,
  });
}

describe('GameContext', () => {
  it('provides initial state', () => {
    const { result } = renderUseGame();
    expect(result.current.state).toEqual({
      games: [],
      selectedGame: null,
      turnSnapshots: [],
      currentTurn: 0,
      speed: 1,
      playing: false,
    });
  });

  it('throws when useGame is used outside GameProvider', () => {
    expect(() => {
      renderHook(() => useGame());
    }).toThrow('useGame must be used within a GameProvider');
  });

  describe('LOAD_GAMES', () => {
    it('stores parsed games and resets selection', () => {
      const { result } = renderUseGame();
      const games = [createMockGame(), createMockGame({ game_id: 'test-game-2' })];

      act(() => {
        result.current.dispatch({ type: 'LOAD_GAMES', payload: { games } });
      });

      expect(result.current.state.games).toHaveLength(2);
      expect(result.current.state.selectedGame).toBeNull();
      expect(result.current.state.currentTurn).toBe(0);
      expect(result.current.state.playing).toBe(false);
    });
  });

  describe('SELECT_GAME', () => {
    it('stores the game and computes turn snapshots', () => {
      const { result } = renderUseGame();
      const game = createMockGame();

      act(() => {
        result.current.dispatch({ type: 'SELECT_GAME', payload: game });
      });

      expect(result.current.state.selectedGame).toBe(game);
      expect(result.current.state.turnSnapshots.length).toBe(3); // turn 0, 1, 2
      expect(result.current.state.currentTurn).toBe(0);
      expect(result.current.state.playing).toBe(false);
    });

    it('resets turn to 0 when selecting a new game', () => {
      const { result } = renderUseGame();
      const game = createMockGame();

      act(() => {
        result.current.dispatch({ type: 'SELECT_GAME', payload: game });
      });
      act(() => {
        result.current.dispatch({ type: 'SET_TURN', payload: 2 });
      });
      act(() => {
        result.current.dispatch({ type: 'SELECT_GAME', payload: createMockGame({ game_id: 'other' }) });
      });

      expect(result.current.state.currentTurn).toBe(0);
    });
  });

  describe('SET_TURN', () => {
    it('sets the turn within valid bounds', () => {
      const { result } = renderUseGame();
      const game = createMockGame();

      act(() => {
        result.current.dispatch({ type: 'SELECT_GAME', payload: game });
      });
      act(() => {
        result.current.dispatch({ type: 'SET_TURN', payload: 1 });
      });

      expect(result.current.state.currentTurn).toBe(1);
    });

    it('clamps turn to 0 when negative', () => {
      const { result } = renderUseGame();
      const game = createMockGame();

      act(() => {
        result.current.dispatch({ type: 'SELECT_GAME', payload: game });
      });
      act(() => {
        result.current.dispatch({ type: 'SET_TURN', payload: -5 });
      });

      expect(result.current.state.currentTurn).toBe(0);
    });

    it('clamps turn to max when exceeding total turns', () => {
      const { result } = renderUseGame();
      const game = createMockGame();

      act(() => {
        result.current.dispatch({ type: 'SELECT_GAME', payload: game });
      });
      act(() => {
        result.current.dispatch({ type: 'SET_TURN', payload: 100 });
      });

      // Max turn is turnSnapshots.length - 1 = 2
      expect(result.current.state.currentTurn).toBe(2);
    });
  });

  describe('SET_SPEED', () => {
    it('updates the speed value', () => {
      const { result } = renderUseGame();

      act(() => {
        result.current.dispatch({ type: 'SET_SPEED', payload: 2 });
      });
      expect(result.current.state.speed).toBe(2);

      act(() => {
        result.current.dispatch({ type: 'SET_SPEED', payload: 4 });
      });
      expect(result.current.state.speed).toBe(4);
    });
  });

  describe('TOGGLE_PLAY', () => {
    it('flips the playing state', () => {
      const { result } = renderUseGame();

      expect(result.current.state.playing).toBe(false);

      act(() => {
        result.current.dispatch({ type: 'TOGGLE_PLAY' });
      });
      expect(result.current.state.playing).toBe(true);

      act(() => {
        result.current.dispatch({ type: 'TOGGLE_PLAY' });
      });
      expect(result.current.state.playing).toBe(false);
    });
  });
});
