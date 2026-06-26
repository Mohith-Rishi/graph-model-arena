import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';
import { PlaybackControls, computeInterval } from './PlaybackControls';
import { GameProvider, useGame } from '../context/GameContext';

function createMockGame(turnCount = 5) {
  const eventLog = [];
  for (let t = 1; t <= turnCount; t++) {
    eventLog.push({
      turn: t,
      model_id: 'model_a',
      event_type: 'MOVE',
      details: { target_node: `node_${t}` },
    });
  }

  return {
    game_id: 'test-game',
    timestamp: '2024-01-01T00:00:00Z',
    full_state: {
      graph: {
        start_node: 'node_0',
        end_node: `node_${turnCount}`,
        nodes: { node_0: { id: 'node_0', node_type: 'START' } },
        edges: [],
      },
      models: {
        model_a: { current_node: 'node_0', score: 0 },
      },
      event_log: eventLog,
      current_turn: turnCount,
      max_turns: 50,
    },
  };
}

// Helper to render PlaybackControls with a pre-loaded game
function SetupComponent({ game }) {
  const { dispatch } = useGame();

  // Load the game on mount
  React.useEffect(() => {
    if (game) {
      dispatch({ type: 'SELECT_GAME', payload: game });
    }
  }, []);

  return <PlaybackControls />;
}

import React from 'react';

function renderWithGame(game) {
  return render(
    <GameProvider>
      <SetupComponent game={game} />
    </GameProvider>
  );
}

function renderPlaybackControls() {
  return render(
    <GameProvider>
      <PlaybackControls />
    </GameProvider>
  );
}

describe('computeInterval', () => {
  it('returns 1000 for speed 1', () => {
    expect(computeInterval(1)).toBe(1000);
  });

  it('returns 500 for speed 2', () => {
    expect(computeInterval(2)).toBe(500);
  });

  it('returns 250 for speed 4', () => {
    expect(computeInterval(4)).toBe(250);
  });

  it('returns 666.67 for speed 1.5', () => {
    expect(computeInterval(1.5)).toBeCloseTo(666.67, 1);
  });

  it('returns 333.33 for speed 3', () => {
    expect(computeInterval(3)).toBeCloseTo(333.33, 1);
  });
});

describe('PlaybackControls', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders a range slider with correct initial values when no game loaded', () => {
    renderPlaybackControls();

    const slider = screen.getByRole('slider');
    expect(slider).toBeInTheDocument();
    expect(slider).toHaveAttribute('min', '0');
    expect(slider).toHaveAttribute('max', '0');
    expect(slider).toHaveValue('0');
  });

  it('renders play button initially', () => {
    renderPlaybackControls();

    const button = screen.getByRole('button', { name: 'Play' });
    expect(button).toBeInTheDocument();
  });

  it('renders speed selector buttons', () => {
    renderPlaybackControls();

    expect(screen.getByRole('button', { name: '1x' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '1.5x' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '2x' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '3x' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '4x' })).toBeInTheDocument();
  });

  it('shows correct max turn when game is loaded', () => {
    const game = createMockGame(5);
    renderWithGame(game);

    const slider = screen.getByRole('slider');
    // 5 turns means snapshots for turn 0-5 = 6 snapshots, max = 5
    expect(slider).toHaveAttribute('max', '5');
  });

  it('dispatches SET_TURN when slider changes', () => {
    const game = createMockGame(5);
    renderWithGame(game);

    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '3' } });

    expect(slider).toHaveValue('3');
    expect(screen.getByText(/Turn: 3 \/ 5/)).toBeInTheDocument();
  });

  it('toggles play/pause button text on click', () => {
    renderPlaybackControls();

    const button = screen.getByRole('button', { name: 'Play' });
    fireEvent.click(button);

    expect(screen.getByRole('button', { name: 'Pause' })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Pause' }));
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument();
  });

  it('marks the active speed button with aria-pressed', () => {
    renderPlaybackControls();

    const btn1x = screen.getByRole('button', { name: '1x' });
    expect(btn1x).toHaveAttribute('aria-pressed', 'true');

    const btn2x = screen.getByRole('button', { name: '2x' });
    expect(btn2x).toHaveAttribute('aria-pressed', 'false');
  });

  it('changes speed when a speed button is clicked', () => {
    renderPlaybackControls();

    const btn2x = screen.getByRole('button', { name: '2x' });
    fireEvent.click(btn2x);

    expect(btn2x).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByRole('button', { name: '1x' })).toHaveAttribute('aria-pressed', 'false');
  });

  it('auto-advances turn when playing at default speed', () => {
    const game = createMockGame(5);
    renderWithGame(game);

    // Start playing
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));

    // Advance one interval (1000ms at 1x speed)
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByRole('slider')).toHaveValue('1');

    // Advance another interval
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    expect(screen.getByRole('slider')).toHaveValue('2');
  });

  it('auto-advances faster at higher speed', () => {
    const game = createMockGame(5);
    renderWithGame(game);

    // Set speed to 2x
    fireEvent.click(screen.getByRole('button', { name: '2x' }));

    // Start playing
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));

    // At 2x speed, interval is 500ms
    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(screen.getByRole('slider')).toHaveValue('1');

    act(() => {
      vi.advanceTimersByTime(500);
    });

    expect(screen.getByRole('slider')).toHaveValue('2');
  });

  it('stops auto-advance when reaching max turn', () => {
    const game = createMockGame(2); // only 2 turns + turn 0 = 3 snapshots, max = 2
    renderWithGame(game);

    // Start playing
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));

    // Advance through all turns
    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByRole('slider')).toHaveValue('1');

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByRole('slider')).toHaveValue('2');

    // Next tick should stop (TOGGLE_PLAY)
    act(() => {
      vi.advanceTimersByTime(1000);
    });

    // Should now show Play button (stopped)
    expect(screen.getByRole('button', { name: 'Play' })).toBeInTheDocument();
    // Turn should still be at max
    expect(screen.getByRole('slider')).toHaveValue('2');
  });

  it('stops interval when pause is clicked during playback', () => {
    const game = createMockGame(5);
    renderWithGame(game);

    // Start playing
    fireEvent.click(screen.getByRole('button', { name: 'Play' }));

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByRole('slider')).toHaveValue('1');

    // Pause
    fireEvent.click(screen.getByRole('button', { name: 'Pause' }));

    // Further time should not advance the turn
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(screen.getByRole('slider')).toHaveValue('1');
  });

  it('displays turn label correctly', () => {
    const game = createMockGame(10);
    renderWithGame(game);

    expect(screen.getByText(/Turn: 0 \/ 10/)).toBeInTheDocument();

    const slider = screen.getByRole('slider');
    fireEvent.change(slider, { target: { value: '7' } });

    expect(screen.getByText(/Turn: 7 \/ 10/)).toBeInTheDocument();
  });
});
