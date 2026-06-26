import { useMemo } from 'react';
import { useGame } from '../context/GameContext';
import { PLAYER_COLORS } from '../constants/colors';

/**
 * Builds the player legend entries with color and strategy name.
 * Exported for testing purposes.
 *
 * @param {object} selectedGame - The selected game object
 * @returns {Array} Array of { modelId, strategyName, color }
 */
export function buildLegendEntries(selectedGame) {
  if (!selectedGame) return [];

  let playerOrder = [];

  if (selectedGame.rankings && selectedGame.rankings.length > 0) {
    playerOrder = selectedGame.rankings.map((r) => ({
      modelId: r.model_id,
      strategyName: r.strategy_name || r.model_id,
    }));
  } else if (selectedGame.full_state?.models) {
    playerOrder = Object.keys(selectedGame.full_state.models).map((modelId) => ({
      modelId,
      strategyName: modelId,
    }));
  }

  return playerOrder.map((player, index) => ({
    modelId: player.modelId,
    strategyName: player.strategyName,
    color: PLAYER_COLORS[index % PLAYER_COLORS.length],
  }));
}

export function PlayerLegend() {
  const { state } = useGame();
  const { selectedGame } = state;

  const entries = useMemo(() => buildLegendEntries(selectedGame), [selectedGame]);

  if (!selectedGame || entries.length === 0) {
    return null;
  }

  return (
    <div className="player-legend">
      <h3>Players</h3>
      <ul aria-label="Player legend">
        {entries.map((entry) => (
          <li key={entry.modelId} className="legend-item">
            <span
              className="legend-swatch"
              style={{ backgroundColor: entry.color }}
              aria-hidden="true"
            />
            <span className="legend-name">{entry.strategyName}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
