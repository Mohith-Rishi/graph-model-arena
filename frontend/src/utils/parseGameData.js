/**
 * Parses and validates a raw JSON string containing game result data.
 *
 * @param {string} jsonString - Raw JSON string from a game_results.json file
 * @returns {{ success: true, games: Array } | { success: false, error: string }}
 */
export function parseGameData(jsonString) {
  let parsed;

  try {
    parsed = JSON.parse(jsonString);
  } catch {
    return {
      success: false,
      error: 'Invalid JSON file. Please upload a valid game_results.json',
    };
  }

  if (!Array.isArray(parsed)) {
    return {
      success: false,
      error: 'Expected an array of game results',
    };
  }

  if (parsed.length === 0) {
    return { success: true, games: [] };
  }

  for (const game of parsed) {
    if (!game.game_id || !game.timestamp) {
      return {
        success: false,
        error: 'Game data incomplete — game_id and timestamp are required',
      };
    }

    if (!game.full_state) {
      return {
        success: false,
        error: 'Game data incomplete — full_state is required for visualization',
      };
    }

    const { full_state } = game;
    if (!full_state.graph || !full_state.models || !full_state.event_log) {
      return {
        success: false,
        error: 'Game data incomplete — full_state must contain graph, models, and event_log',
      };
    }
  }

  // Sort games by timestamp descending (most recent first)
  const sortedGames = [...parsed].sort(
    (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime()
  );

  return { success: true, games: sortedGames };
}
