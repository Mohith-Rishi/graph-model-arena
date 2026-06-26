import { useGame } from '../context/GameContext';

/**
 * Formats event details into a human-readable summary string.
 * Exported for testing purposes.
 *
 * @param {string} eventType - The event type (e.g., 'MOVE', 'POINTS_COLLECTED')
 * @param {object} details - The event details object
 * @returns {string} Formatted details string
 */
export function formatEventDetails(eventType, details) {
  if (!details) return '';

  switch (eventType) {
    case 'MOVE':
      return details.target_node ? `→ ${details.target_node}` : '';
    case 'POINTS_COLLECTED':
      return details.points_awarded != null ? `+${details.points_awarded} pts` : '';
    case 'INVALID_MOVE':
      return details.attempted_node
        ? `tried ${details.attempted_node}`
        : details.reason || '';
    case 'TRAP_RESPAWN_START':
      return details.death_penalty != null
        ? `−${details.death_penalty} pts, back to start`
        : 'back to start';
    case 'TRAP_RESPAWN_CHECKPOINT':
      return details.trap_respawn_penalty != null
        ? `−${details.trap_respawn_penalty} pts, back to checkpoint`
        : 'back to checkpoint';
    case 'GAME_FINISHED':
      return 'finished';
    default:
      return JSON.stringify(details);
  }
}

/**
 * Builds the list of event entries for rendering.
 * Exported for testing purposes.
 *
 * @param {Array} eventLog - The raw event log array
 * @param {Array} rankings - Rankings array from the selected game
 * @returns {Array} Array of formatted event entries
 */
export function buildEventEntries(eventLog, rankings) {
  if (!eventLog || !Array.isArray(eventLog)) return [];

  const nameMap = {};
  if (rankings && Array.isArray(rankings)) {
    rankings.forEach((r) => {
      if (r.model_id) {
        nameMap[r.model_id] = r.strategy_name || r.model_id;
      }
    });
  }

  return eventLog.map((event, index) => ({
    index,
    turn: event.turn,
    modelId: event.model_id,
    strategyName: nameMap[event.model_id] || event.model_id,
    eventType: event.event_type,
    details: formatEventDetails(event.event_type, event.details),
  }));
}

export function EventLog() {
  const { state, dispatch } = useGame();
  const { selectedGame, currentTurn } = state;

  if (!selectedGame) {
    return null;
  }

  const eventLog = selectedGame.full_state?.event_log ?? [];
  const rankings = selectedGame.rankings ?? [];
  const entries = buildEventEntries(eventLog, rankings);

  function handleEventClick(turn) {
    dispatch({ type: 'SET_TURN', payload: turn });
  }

  return (
    <div className="event-log" style={{ maxHeight: '400px', overflowY: 'auto' }}>
      <h3>Event Log</h3>
      <table>
        <thead>
          <tr>
            <th>Turn</th>
            <th>Player</th>
            <th>Event</th>
            <th>Details</th>
          </tr>
        </thead>
        <tbody>
          {entries.map((entry) => {
            const isHighlighted = entry.turn <= currentTurn;
            return (
              <tr
                key={entry.index}
                className={isHighlighted ? 'event-highlighted' : 'event-dimmed'}
                style={{
                  opacity: isHighlighted ? 1 : 0.4,
                  fontWeight: isHighlighted ? 'bold' : 'normal',
                  cursor: 'pointer',
                }}
                onClick={() => handleEventClick(entry.turn)}
              >
                <td>{entry.turn}</td>
                <td>{entry.strategyName}</td>
                <td>{entry.eventType}</td>
                <td>{entry.details}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
