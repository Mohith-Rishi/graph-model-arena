import { useGame } from '../context/GameContext';

/**
 * Builds a sorted list of player entries for the scoreboard.
 * Exported for testing purposes.
 *
 * @param {object} snapshot - TurnSnapshot for the current turn
 * @param {object} selectedGame - The selected game object (with rankings)
 * @returns {Array} Sorted array of player objects
 */
export function buildPlayerList(snapshot, selectedGame) {
  if (!snapshot) return [];

  const { playerPositions, playerScores, playerStatuses } = snapshot;
  const modelIds = Object.keys(playerScores);

  const players = modelIds.map((modelId) => {
    // Derive strategy name from rankings
    let strategyName = modelId;
    if (selectedGame?.rankings) {
      const ranking = selectedGame.rankings.find(
        (r) => r.model_id === modelId
      );
      if (ranking?.strategy_name) {
        strategyName = ranking.strategy_name;
      }
    }

    return {
      modelId,
      strategyName,
      score: playerScores[modelId] ?? 0,
      currentNode: playerPositions[modelId] ?? '',
      status: playerStatuses[modelId] ?? 'active',
    };
  });

  // Sort by score descending
  players.sort((a, b) => b.score - a.score);

  return players;
}

export function Scoreboard() {
  const { state } = useGame();
  const { turnSnapshots, currentTurn, selectedGame } = state;

  const snapshot = turnSnapshots[currentTurn] ?? null;
  const players = buildPlayerList(snapshot, selectedGame);

  if (!selectedGame) {
    return null;
  }

  return (
    <div className="scoreboard">
      <h3>Scoreboard</h3>
      <table>
        <thead>
          <tr>
            <th>Strategy</th>
            <th>Score</th>
            <th>Current Node</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody>
          {players.map((player) => (
            <tr key={player.modelId}>
              <td>{player.strategyName}</td>
              <td>{player.score}</td>
              <td>{player.currentNode}</td>
              <td>{player.status === 'finished' ? '✓' : ''}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
