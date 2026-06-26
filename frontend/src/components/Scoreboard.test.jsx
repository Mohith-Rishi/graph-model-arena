import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { Scoreboard, buildPlayerList } from './Scoreboard';
import { GameProvider, useGame } from '../context/GameContext';

function createMockGame() {
  return {
    game_id: 'test-game',
    timestamp: '2024-01-01T00:00:00Z',
    rankings: [
      { model_id: 'model_a', strategy_name: 'AlphaStrategy', rank: 1, final_score: 20 },
      { model_id: 'model_b', strategy_name: 'BetaStrategy', rank: 2, final_score: 10 },
      { model_id: 'model_c', strategy_name: 'GammaStrategy', rank: 3, final_score: 5 },
    ],
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
        model_c: { current_node: 'node_0', score: 0 },
      },
      event_log: [
        { turn: 1, model_id: 'model_a', event_type: 'MOVE', details: { target_node: 'node_1' } },
        { turn: 1, model_id: 'model_b', event_type: 'MOVE', details: { target_node: 'node_2' } },
        { turn: 1, model_id: 'model_c', event_type: 'MOVE', details: { target_node: 'node_3' } },
        { turn: 1, model_id: 'model_a', event_type: 'POINTS_COLLECTED', details: { points_awarded: 15 } },
        { turn: 1, model_id: 'model_b', event_type: 'POINTS_COLLECTED', details: { points_awarded: 10 } },
        { turn: 2, model_id: 'model_a', event_type: 'GAME_FINISHED', details: {} },
      ],
      current_turn: 2,
      max_turns: 50,
    },
  };
}

// Helper component to load game then render Scoreboard
function SetupComponent({ game, turn }) {
  const { dispatch } = useGame();

  React.useEffect(() => {
    if (game) {
      dispatch({ type: 'SELECT_GAME', payload: game });
    }
  }, []);

  React.useEffect(() => {
    if (turn !== undefined && turn > 0) {
      dispatch({ type: 'SET_TURN', payload: turn });
    }
  }, [turn]);

  return <Scoreboard />;
}

function renderWithGame(game, turn) {
  return render(
    <GameProvider>
      <SetupComponent game={game} turn={turn} />
    </GameProvider>
  );
}

describe('buildPlayerList', () => {
  it('returns empty array when snapshot is null', () => {
    expect(buildPlayerList(null, null)).toEqual([]);
  });

  it('returns players sorted by score descending', () => {
    const snapshot = {
      playerPositions: { model_a: 'node_1', model_b: 'node_2', model_c: 'node_3' },
      playerScores: { model_a: 5, model_b: 20, model_c: 10 },
      playerStatuses: { model_a: 'active', model_b: 'active', model_c: 'finished' },
    };
    const game = {
      rankings: [
        { model_id: 'model_a', strategy_name: 'Alpha' },
        { model_id: 'model_b', strategy_name: 'Beta' },
        { model_id: 'model_c', strategy_name: 'Gamma' },
      ],
    };

    const result = buildPlayerList(snapshot, game);

    expect(result).toHaveLength(3);
    expect(result[0].modelId).toBe('model_b');
    expect(result[0].score).toBe(20);
    expect(result[1].modelId).toBe('model_c');
    expect(result[1].score).toBe(10);
    expect(result[2].modelId).toBe('model_a');
    expect(result[2].score).toBe(5);
  });

  it('uses model_id as fallback when strategy_name not found', () => {
    const snapshot = {
      playerPositions: { model_x: 'node_1' },
      playerScores: { model_x: 0 },
      playerStatuses: { model_x: 'active' },
    };

    const result = buildPlayerList(snapshot, { rankings: [] });

    expect(result[0].strategyName).toBe('model_x');
  });

  it('uses model_id when selectedGame has no rankings', () => {
    const snapshot = {
      playerPositions: { model_x: 'node_1' },
      playerScores: { model_x: 0 },
      playerStatuses: { model_x: 'active' },
    };

    const result = buildPlayerList(snapshot, null);

    expect(result[0].strategyName).toBe('model_x');
  });

  it('includes correct currentNode and status', () => {
    const snapshot = {
      playerPositions: { model_a: 'node_5' },
      playerScores: { model_a: 30 },
      playerStatuses: { model_a: 'finished' },
    };
    const game = {
      rankings: [{ model_id: 'model_a', strategy_name: 'Alpha' }],
    };

    const result = buildPlayerList(snapshot, game);

    expect(result[0].currentNode).toBe('node_5');
    expect(result[0].status).toBe('finished');
  });
});

describe('Scoreboard', () => {
  it('renders nothing when no game is selected', () => {
    const { container } = render(
      <GameProvider>
        <Scoreboard />
      </GameProvider>
    );

    expect(container.querySelector('.scoreboard')).toBeNull();
  });

  it('renders a table with column headers', () => {
    const game = createMockGame();
    renderWithGame(game);

    expect(screen.getByText('Strategy')).toBeInTheDocument();
    expect(screen.getByText('Score')).toBeInTheDocument();
    expect(screen.getByText('Current Node')).toBeInTheDocument();
    expect(screen.getByText('Status')).toBeInTheDocument();
  });

  it('renders all players at turn 0 with initial state', () => {
    const game = createMockGame();
    renderWithGame(game, 0);

    // All players should be listed
    expect(screen.getByText('AlphaStrategy')).toBeInTheDocument();
    expect(screen.getByText('BetaStrategy')).toBeInTheDocument();
    expect(screen.getByText('GammaStrategy')).toBeInTheDocument();
  });

  it('shows updated scores at turn 1', () => {
    const game = createMockGame();
    renderWithGame(game, 1);

    // At turn 1, model_a has 15 points, model_b has 10
    const rows = screen.getAllByRole('row');
    // Header + 3 players = 4 rows
    expect(rows).toHaveLength(4);

    // First row (highest score) should be AlphaStrategy with 15
    expect(rows[1]).toHaveTextContent('AlphaStrategy');
    expect(rows[1]).toHaveTextContent('15');
    expect(rows[1]).toHaveTextContent('node_1');

    // Second row should be BetaStrategy with 10
    expect(rows[2]).toHaveTextContent('BetaStrategy');
    expect(rows[2]).toHaveTextContent('10');
    expect(rows[2]).toHaveTextContent('node_2');
  });

  it('shows checkmark for finished players at turn 2', () => {
    const game = createMockGame();
    renderWithGame(game, 2);

    const rows = screen.getAllByRole('row');
    // model_a finished at turn 2
    // AlphaStrategy should have checkmark
    expect(rows[1]).toHaveTextContent('AlphaStrategy');
    expect(rows[1]).toHaveTextContent('✓');
  });

  it('does not show checkmark for active players', () => {
    const game = createMockGame();
    renderWithGame(game, 1);

    const rows = screen.getAllByRole('row');
    // No player should have a checkmark at turn 1
    for (let i = 1; i < rows.length; i++) {
      const statusCell = rows[i].querySelectorAll('td')[3];
      expect(statusCell.textContent).toBe('');
    }
  });

  it('displays scoreboard heading', () => {
    const game = createMockGame();
    renderWithGame(game);

    expect(screen.getByRole('heading', { name: 'Scoreboard' })).toBeInTheDocument();
  });
});
