/**
 * Computes turn-by-turn snapshots of game state from the event log.
 *
 * Takes the full game state (graph, models, event_log, current_turn, max_turns)
 * and derives an array of TurnSnapshot objects, one per turn.
 *
 * Each TurnSnapshot contains:
 *   - turn: the turn number
 *   - playerPositions: { [modelId]: nodeId }
 *   - playerScores: { [modelId]: number }
 *   - playerStatuses: { [modelId]: 'active' | 'finished' }
 *   - eventsThisTurn: array of events that occurred on this turn
 *
 * @param {object} fullState - The full_state object from a game result
 * @param {object} fullState.graph - Graph with start_node, end_node, nodes, edges
 * @param {object} fullState.models - Map of model_id to model state
 * @param {Array} fullState.event_log - Chronological list of game events
 * @param {number} fullState.current_turn - The current/final turn number
 * @param {number} fullState.max_turns - Maximum allowed turns
 * @returns {Array<TurnSnapshot>} Array of snapshots indexed by turn number
 */
export function computeTurnSnapshots(fullState) {
  const { graph, models, event_log: eventLog, current_turn: currentTurn } = fullState;
  const startNode = graph.start_node;
  const modelIds = Object.keys(models);

  // Determine the max turn to build snapshots up to
  const maxEventTurn = eventLog.length > 0
    ? Math.max(...eventLog.map((e) => e.turn))
    : 0;
  const totalTurns = Math.max(maxEventTurn, currentTurn || 0);

  // Group events by turn for efficient lookup
  const eventsByTurn = {};
  for (const event of eventLog) {
    const turn = event.turn;
    if (!eventsByTurn[turn]) {
      eventsByTurn[turn] = [];
    }
    eventsByTurn[turn].push(event);
  }

  // Build turn 0: initial state
  const initialPositions = {};
  const initialScores = {};
  const initialStatuses = {};
  for (const modelId of modelIds) {
    initialPositions[modelId] = startNode;
    initialScores[modelId] = 0;
    initialStatuses[modelId] = 'active';
  }

  const snapshots = [
    {
      turn: 0,
      playerPositions: { ...initialPositions },
      playerScores: { ...initialScores },
      playerStatuses: { ...initialStatuses },
      eventsThisTurn: [],
    },
  ];

  // Build subsequent turns by applying events
  for (let turn = 1; turn <= totalTurns; turn++) {
    const prevSnapshot = snapshots[turn - 1];
    const positions = { ...prevSnapshot.playerPositions };
    const scores = { ...prevSnapshot.playerScores };
    const statuses = { ...prevSnapshot.playerStatuses };
    const turnEvents = eventsByTurn[turn] || [];

    for (const event of turnEvents) {
      const { model_id: modelId, event_type: eventType, details } = event;

      // Skip events for unknown models
      if (!modelIds.includes(modelId)) {
        console.warn(`Unknown model_id in event: ${modelId}`);
        continue;
      }

      switch (eventType) {
        case 'MOVE':
          positions[modelId] = details.target_node || details.to_node;
          break;

        case 'POINTS_COLLECTED':
          scores[modelId] += details.points_awarded || details.points || 0;
          break;

        case 'TRAP_RESPAWN_START':
          positions[modelId] = startNode;
          scores[modelId] -= details.death_penalty || details.penalty || 0;
          break;

        case 'TRAP_RESPAWN_CHECKPOINT':
          positions[modelId] = details.checkpoint || details.checkpoint_node;
          scores[modelId] -= details.trap_respawn_penalty || details.penalty || 0;
          break;

        case 'INVALID_MOVE':
          scores[modelId] -= details.invalid_move_penalty || details.penalty || 0;
          break;

        case 'GAME_FINISHED':
          statuses[modelId] = 'finished';
          break;

        default:
          // Unknown event type — skip silently
          break;
      }
    }

    snapshots.push({
      turn,
      playerPositions: positions,
      playerScores: scores,
      playerStatuses: statuses,
      eventsThisTurn: turnEvents,
    });
  }

  return snapshots;
}
