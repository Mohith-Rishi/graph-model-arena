import { useGame } from '../context/GameContext';

function formatTimestamp(timestamp) {
  try {
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) {
      return timestamp;
    }
    return date.toLocaleString();
  } catch {
    return timestamp;
  }
}

export function GameSelector() {
  const { state, dispatch } = useGame();

  if (!state.games || state.games.length === 0) {
    return <p>No games found in this file</p>;
  }

  function handleSelect(game) {
    dispatch({ type: 'SELECT_GAME', payload: game });
  }

  return (
    <div className="game-selector">
      <h2>Select a Game</h2>
      <ul role="list" aria-label="Available games">
        {state.games.map((game) => (
          <li key={game.game_id}>
            <button
              type="button"
              onClick={() => handleSelect(game)}
              aria-label={`Select game ${game.game_id}`}
            >
              <span className="game-id">{game.game_id}</span>
              <span className="game-timestamp">{formatTimestamp(game.timestamp)}</span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
