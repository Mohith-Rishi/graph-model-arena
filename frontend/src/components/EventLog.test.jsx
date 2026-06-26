import React from 'react';
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EventLog, formatEventDetails, buildEventEntries } from './EventLog';
import { GameProvider, useGame } from '../context/GameContext';

function createMockGame() {
  return {
    game_id: 'test-game',
    timestamp: '2024-01-01T00:00:00Z',
    rankings: [
      { model_id: 'model_a', strategy_name: 'AlphaStrategy', rank: 1, final_score: 20 },
      { model_id: 'model_b', strategy_name: 'BetaStrategy', rank: 2, final_score: 10 },
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
      },
      event_log: [
        { turn: 1, model_id: 'model_a', event_type: 'MOVE', details: { target_node: 'node_1' } },
        { turn: 1, model_id: 'model_b', event_type: 'MOVE', details: { target_node: 'node_2' } },
        { turn: 2, model_id: 'model_a', event_type: 'POINTS_COLLECTED', details: { points_awarded: 10 } },
        { turn: 3, model_id: 'model_a', event_type: 'GAME_FINISHED', details: {} },
      ],
      current_turn: 3,
      max_turns: 50,
    },
  };
}

// Helper component to load game then render EventLog
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

  return <EventLog />;
}

function renderWithGame(game, turn) {
  return render(
    <GameProvider>
      <SetupComponent game={game} turn={turn} />
    </GameProvider>
  );
}

describe('formatEventDetails', () => {
  it('formats MOVE events with target node', () => {
    expect(formatEventDetails('MOVE', { target_node: 'node_3' })).toBe('→ node_3');
  });

  it('formats POINTS_COLLECTED events with points', () => {
    expect(formatEventDetails('POINTS_COLLECTED', { points_awarded: 15 })).toBe('+15 pts');
  });

  it('formats INVALID_MOVE with attempted node', () => {
    expect(formatEventDetails('INVALID_MOVE', { attempted_node: 'node_9' })).toBe('tried node_9');
  });

  it('formats INVALID_MOVE with reason fallback', () => {
    expect(formatEventDetails('INVALID_MOVE', { reason: 'no edge' })).toBe('no edge');
  });

  it('formats TRAP_RESPAWN_START with penalty', () => {
    expect(formatEventDetails('TRAP_RESPAWN_START', { death_penalty: 5 })).toBe('−5 pts, back to start');
  });

  it('formats TRAP_RESPAWN_START without penalty', () => {
    expect(formatEventDetails('TRAP_RESPAWN_START', {})).toBe('back to start');
  });

  it('formats TRAP_RESPAWN_CHECKPOINT with penalty', () => {
    expect(formatEventDetails('TRAP_RESPAWN_CHECKPOINT', { trap_respawn_penalty: 3 })).toBe('−3 pts, back to checkpoint');
  });

  it('formats TRAP_RESPAWN_CHECKPOINT without penalty', () => {
    expect(formatEventDetails('TRAP_RESPAWN_CHECKPOINT', {})).toBe('back to checkpoint');
  });

  it('formats GAME_FINISHED', () => {
    expect(formatEventDetails('GAME_FINISHED', {})).toBe('finished');
  });

  it('returns JSON string for unknown event types', () => {
    const details = { custom: 'data' };
    expect(formatEventDetails('UNKNOWN_EVENT', details)).toBe(JSON.stringify(details));
  });

  it('returns empty string for null details', () => {
    expect(formatEventDetails('MOVE', null)).toBe('');
  });
});

describe('buildEventEntries', () => {
  it('returns empty array when eventLog is null', () => {
    expect(buildEventEntries(null, [])).toEqual([]);
  });

  it('returns empty array when eventLog is not an array', () => {
    expect(buildEventEntries('invalid', [])).toEqual([]);
  });

  it('maps model_id to strategy_name from rankings', () => {
    const eventLog = [
      { turn: 1, model_id: 'model_a', event_type: 'MOVE', details: { target_node: 'node_1' } },
    ];
    const rankings = [{ model_id: 'model_a', strategy_name: 'AlphaStrategy' }];

    const result = buildEventEntries(eventLog, rankings);

    expect(result[0].strategyName).toBe('AlphaStrategy');
  });

  it('uses model_id as fallback when not in rankings', () => {
    const eventLog = [
      { turn: 1, model_id: 'model_x', event_type: 'MOVE', details: { target_node: 'node_1' } },
    ];
    const rankings = [{ model_id: 'model_a', strategy_name: 'AlphaStrategy' }];

    const result = buildEventEntries(eventLog, rankings);

    expect(result[0].strategyName).toBe('model_x');
  });

  it('builds correct entries with all fields', () => {
    const eventLog = [
      { turn: 2, model_id: 'model_b', event_type: 'POINTS_COLLECTED', details: { points_awarded: 5 } },
    ];
    const rankings = [{ model_id: 'model_b', strategy_name: 'Beta' }];

    const result = buildEventEntries(eventLog, rankings);

    expect(result[0]).toEqual({
      index: 0,
      turn: 2,
      modelId: 'model_b',
      strategyName: 'Beta',
      eventType: 'POINTS_COLLECTED',
      details: '+5 pts',
    });
  });

  it('handles null rankings gracefully', () => {
    const eventLog = [
      { turn: 1, model_id: 'model_a', event_type: 'MOVE', details: { target_node: 'node_1' } },
    ];

    const result = buildEventEntries(eventLog, null);

    expect(result[0].strategyName).toBe('model_a');
  });
});

describe('EventLog', () => {
  it('renders nothing when no game is selected', () => {
    const { container } = render(
      <GameProvider>
        <EventLog />
      </GameProvider>
    );

    expect(container.querySelector('.event-log')).toBeNull();
  });

  it('renders the Event Log heading', () => {
    const game = createMockGame();
    renderWithGame(game);

    expect(screen.getByRole('heading', { name: 'Event Log' })).toBeInTheDocument();
  });

  it('renders table column headers', () => {
    const game = createMockGame();
    renderWithGame(game);

    expect(screen.getByText('Turn')).toBeInTheDocument();
    expect(screen.getByText('Player')).toBeInTheDocument();
    expect(screen.getByText('Event')).toBeInTheDocument();
    expect(screen.getByText('Details')).toBeInTheDocument();
  });

  it('renders all events from the event log', () => {
    const game = createMockGame();
    renderWithGame(game);

    const rows = screen.getAllByRole('row');
    // Header + 4 events = 5 rows
    expect(rows).toHaveLength(5);
  });

  it('displays strategy names from rankings', () => {
    const game = createMockGame();
    renderWithGame(game);

    expect(screen.getAllByText('AlphaStrategy').length).toBeGreaterThan(0);
    expect(screen.getAllByText('BetaStrategy').length).toBeGreaterThan(0);
  });

  it('displays formatted event details', () => {
    const game = createMockGame();
    renderWithGame(game);

    expect(screen.getByText('→ node_1')).toBeInTheDocument();
    expect(screen.getByText('→ node_2')).toBeInTheDocument();
    expect(screen.getByText('+10 pts')).toBeInTheDocument();
    expect(screen.getByText('finished')).toBeInTheDocument();
  });

  it('highlights events at or before current turn', () => {
    const game = createMockGame();
    renderWithGame(game, 2);

    const rows = screen.getAllByRole('row');
    // Events at turn 1 and 2 (rows 1, 2, 3) should be highlighted
    expect(rows[1]).toHaveClass('event-highlighted');
    expect(rows[2]).toHaveClass('event-highlighted');
    expect(rows[3]).toHaveClass('event-highlighted');
    // Event at turn 3 (row 4) should be dimmed
    expect(rows[4]).toHaveClass('event-dimmed');
  });

  it('dims events after current turn', () => {
    const game = createMockGame();
    renderWithGame(game, 1);

    const rows = screen.getAllByRole('row');
    // Events at turn 1 (rows 1, 2) highlighted; turns 2, 3 (rows 3, 4) dimmed
    expect(rows[1]).toHaveClass('event-highlighted');
    expect(rows[2]).toHaveClass('event-highlighted');
    expect(rows[3]).toHaveClass('event-dimmed');
    expect(rows[4]).toHaveClass('event-dimmed');
  });

  it('dispatches SET_TURN when an event row is clicked', () => {
    const game = createMockGame();
    renderWithGame(game, 1);

    const rows = screen.getAllByRole('row');
    // Click on the event at turn 3 (row 4)
    fireEvent.click(rows[4]);

    // After clicking, the turn 3 event should now be highlighted
    // (since currentTurn should have jumped to 3)
    expect(rows[4]).toHaveClass('event-highlighted');
  });

  it('panel has scrollable container', () => {
    const game = createMockGame();
    const { container } = renderWithGame(game);

    const panel = container.querySelector('.event-log');
    expect(panel).not.toBeNull();
    expect(panel.style.maxHeight).toBe('400px');
    expect(panel.style.overflowY).toBe('auto');
  });
});
