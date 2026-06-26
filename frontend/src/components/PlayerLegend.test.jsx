import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { buildLegendEntries, PlayerLegend } from './PlayerLegend';
import { GameProvider } from '../context/GameContext';
import { PLAYER_COLORS } from '../constants/colors';

describe('buildLegendEntries', () => {
  it('returns empty array when selectedGame is null', () => {
    expect(buildLegendEntries(null)).toEqual([]);
  });

  it('builds entries from rankings', () => {
    const game = {
      rankings: [
        { model_id: 'model_1', strategy_name: 'AlphaStrat' },
        { model_id: 'model_2', strategy_name: 'BetaStrat' },
      ],
      full_state: { models: {} },
    };

    const entries = buildLegendEntries(game);
    expect(entries).toHaveLength(2);
    expect(entries[0]).toEqual({
      modelId: 'model_1',
      strategyName: 'AlphaStrat',
      color: PLAYER_COLORS[0],
    });
    expect(entries[1]).toEqual({
      modelId: 'model_2',
      strategyName: 'BetaStrat',
      color: PLAYER_COLORS[1],
    });
  });

  it('falls back to model keys when rankings are empty', () => {
    const game = {
      rankings: [],
      full_state: {
        models: {
          modelA: { current_node: 'n1' },
          modelB: { current_node: 'n2' },
        },
      },
    };

    const entries = buildLegendEntries(game);
    expect(entries).toHaveLength(2);
    expect(entries[0].modelId).toBe('modelA');
    expect(entries[0].strategyName).toBe('modelA');
    expect(entries[1].modelId).toBe('modelB');
  });

  it('wraps colors when more players than palette entries', () => {
    const rankings = Array.from({ length: 10 }, (_, i) => ({
      model_id: `model_${i}`,
      strategy_name: `Strategy ${i}`,
    }));
    const game = { rankings, full_state: { models: {} } };

    const entries = buildLegendEntries(game);
    expect(entries).toHaveLength(10);
    // 9th player (index 8) wraps to PLAYER_COLORS[0]
    expect(entries[8].color).toBe(PLAYER_COLORS[0]);
  });

  it('uses model_id as strategy name when strategy_name is missing', () => {
    const game = {
      rankings: [{ model_id: 'model_x' }],
      full_state: { models: {} },
    };

    const entries = buildLegendEntries(game);
    expect(entries[0].strategyName).toBe('model_x');
  });
});

describe('PlayerLegend component', () => {
  it('renders nothing when no game is selected', () => {
    const { container } = render(
      <GameProvider>
        <PlayerLegend />
      </GameProvider>
    );
    expect(container.querySelector('.player-legend')).toBeNull();
  });
});
