import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { GameSelector } from './GameSelector';
import * as GameContext from '../context/GameContext';

function makeGame(overrides = {}) {
  return {
    game_id: 'game-001',
    timestamp: '2024-01-15T10:30:00Z',
    config: {},
    rankings: [],
    graph_stats: {},
    total_turns: 10,
    full_state: {
      graph: { nodes: {}, edges: [], start_node: 'n1', end_node: 'n5' },
      models: { model_a: { current_node: 'n1', score: 0 } },
      event_log: [],
      current_turn: 10,
      max_turns: 50,
    },
    ...overrides,
  };
}

function renderWithContext(state, dispatch = vi.fn()) {
  vi.spyOn(GameContext, 'useGame').mockReturnValue({ state, dispatch });
  return { dispatch, ...render(<GameSelector />) };
}

describe('GameSelector', () => {
  it('renders "No games found" message when games array is empty', () => {
    renderWithContext({ games: [] });
    expect(screen.getByText('No games found in this file')).toBeInTheDocument();
  });

  it('renders "No games found" when games is undefined', () => {
    renderWithContext({ games: undefined });
    expect(screen.getByText('No games found in this file')).toBeInTheDocument();
  });

  it('renders a list of games with game_id and timestamp', () => {
    const games = [
      makeGame({ game_id: 'game-abc', timestamp: '2024-03-20T14:00:00Z' }),
      makeGame({ game_id: 'game-xyz', timestamp: '2024-03-19T09:00:00Z' }),
    ];
    renderWithContext({ games });

    expect(screen.getByText('game-abc')).toBeInTheDocument();
    expect(screen.getByText('game-xyz')).toBeInTheDocument();
    // Timestamps are formatted via toLocaleString, just check they render
    expect(screen.getAllByRole('button')).toHaveLength(2);
  });

  it('dispatches SELECT_GAME with the clicked game', () => {
    const game = makeGame({ game_id: 'game-click' });
    const { dispatch } = renderWithContext({ games: [game] });

    fireEvent.click(screen.getByRole('button', { name: /select game game-click/i }));

    expect(dispatch).toHaveBeenCalledWith({
      type: 'SELECT_GAME',
      payload: game,
    });
  });

  it('renders games in the order provided (pre-sorted descending)', () => {
    const games = [
      makeGame({ game_id: 'newest', timestamp: '2024-12-01T00:00:00Z' }),
      makeGame({ game_id: 'middle', timestamp: '2024-06-01T00:00:00Z' }),
      makeGame({ game_id: 'oldest', timestamp: '2024-01-01T00:00:00Z' }),
    ];
    renderWithContext({ games });

    const buttons = screen.getAllByRole('button');
    expect(buttons[0]).toHaveTextContent('newest');
    expect(buttons[1]).toHaveTextContent('middle');
    expect(buttons[2]).toHaveTextContent('oldest');
  });

  it('displays formatted timestamps for each game', () => {
    const games = [
      makeGame({ game_id: 'game-ts', timestamp: '2024-07-04T12:00:00Z' }),
    ];
    renderWithContext({ games });

    // The timestamp should be rendered (formatted by toLocaleString)
    const button = screen.getByRole('button');
    // It should contain some representation of the date
    expect(button.textContent).toContain('game-ts');
    // Verify the timestamp element exists
    const timestampEl = button.querySelector('.game-timestamp');
    expect(timestampEl).not.toBeNull();
    expect(timestampEl.textContent).not.toBe('');
  });

  it('handles invalid timestamp gracefully by displaying raw string', () => {
    const games = [
      makeGame({ game_id: 'game-bad-ts', timestamp: 'not-a-date' }),
    ];
    renderWithContext({ games });

    const button = screen.getByRole('button');
    const timestampEl = button.querySelector('.game-timestamp');
    expect(timestampEl.textContent).toBe('not-a-date');
  });

  it('renders accessible list with proper aria-label', () => {
    const games = [makeGame()];
    renderWithContext({ games });

    expect(screen.getByRole('list', { name: /available games/i })).toBeInTheDocument();
  });
});
