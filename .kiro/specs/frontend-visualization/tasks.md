# Implementation Plan: Frontend Visualization UI

## Overview

Build a React (JavaScript) single-page application in `frontend/` that visualizes Graph Model Arena game results. Uses Vite for bundling, react-force-graph-2d for graph rendering, fast-check for property testing, and Vitest + React Testing Library for tests.

## Tasks

- [ ] 1. Scaffold the frontend project
  - [x] 1.1 Initialize the `frontend/` directory with Vite + React (JavaScript) template
    - Run `npm create vite@latest frontend -- --template react`
    - Configure Vitest in `vite.config.js`
    - Add dependencies: `react-force-graph-2d`, `fast-check`
    - Add dev dependencies: `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `jsdom`
    - Verify `npm run dev` and `npm test` work
    - _Requirements: 7.3, 7.4_

  - [x] 1.2 Set up project structure and base files
    - Create directories: `src/components/`, `src/context/`, `src/utils/`, `src/constants/`
    - Create `src/constants/colors.js` with NODE_COLORS and PLAYER_COLORS mappings
    - Create placeholder `App.jsx` with basic routing structure
    - _Requirements: 7.3_

- [ ] 2. Implement data parsing and validation
  - [x] 2.1 Create the JSON parser and validator (`src/utils/parseGameData.js`)
    - Parse raw JSON string, validate structure (must have game_id, timestamp, full_state)
    - Validate full_state contains graph, models, event_log
    - Return `{ success: true, games: [...] }` or `{ success: false, error: "..." }`
    - Sort games by timestamp descending
    - _Requirements: 1.2, 1.4_

  - [ ]* 2.2 Write property tests for data parsing
    - **Property 1: Game list ordering**
    - **Property 2: Invalid input error signaling**
    - **Validates: Requirements 1.2, 1.4**

- [ ] 3. Implement turn snapshot computation
  - [x] 3.1 Create turn snapshot engine (`src/utils/computeTurnSnapshots.js`)
    - Initialize all players at start_node with score 0 at turn 0
    - Process event_log to derive position/score changes per turn
    - Handle MOVE, POINTS_COLLECTED, TRAP_RESPAWN_START, TRAP_RESPAWN_CHECKPOINT, INVALID_MOVE, GAME_FINISHED events
    - Return array of TurnSnapshot objects indexed by turn number
    - _Requirements: 4.2, 5.2_

  - [ ]* 3.2 Write property tests for turn snapshot computation
    - **Property 5: Turn snapshot computation correctness**
    - **Validates: Requirements 4.2, 5.2**

- [ ] 4. Implement state management
  - [x] 4.1 Create GameContext and reducer (`src/context/GameContext.jsx`)
    - Implement LOAD_GAMES, SELECT_GAME, SET_TURN, SET_SPEED, TOGGLE_PLAY actions
    - Store parsed games, selected game, current turn, playback speed, playing state
    - Compute turn snapshots when game is selected
    - _Requirements: 1.3, 4.1, 4.3_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement file upload and game selection UI
  - [x] 6.1 Create FileUploader component (`src/components/FileUploader.jsx`)
    - File input accepting .json files
    - Read file with FileReader API
    - Pass content to parseGameData, dispatch LOAD_GAMES
    - Display error messages for invalid files
    - Enforce 50MB file size limit
    - _Requirements: 1.1, 1.4_

  - [x] 6.2 Create GameSelector component (`src/components/GameSelector.jsx`)
    - Display list of games with game_id and timestamp
    - Games already sorted descending by context
    - On click, dispatch SELECT_GAME
    - _Requirements: 1.2, 1.3, 1.5_

- [ ] 7. Implement graph visualization
  - [x] 7.1 Create GraphCanvas component (`src/components/GraphCanvas.jsx`)
    - Use react-force-graph-2d to render nodes and edges
    - Apply NODE_COLORS based on node_type
    - Display point_value label on POINTS nodes
    - Render obstructed edges with dashed style
    - Display edge cost labels
    - Show tooltip on node hover (node ID and type)
    - Render player markers at current positions (colored circles)
    - Offset markers when multiple players on same node
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7, 3.1, 3.2_

  - [ ]* 7.2 Write property tests for node/edge visual mapping
    - **Property 3: Node visual attribute mapping**
    - **Property 4: Edge rendering completeness and style**
    - **Property 10: Player marker presence and distinctness**
    - **Validates: Requirements 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.3**

- [ ] 8. Implement playback controls
  - [x] 8.1 Create PlaybackControls component (`src/components/PlaybackControls.jsx`)
    - Turn slider (range input) from 0 to totalTurns
    - Play/pause button toggling auto-advance
    - SpeedSelector with options: 1x, 1.5x, 2x, 3x, 4x
    - Auto-advance uses setInterval with interval = 1000 / speed ms
    - Dispatch SET_TURN, SET_SPEED, TOGGLE_PLAY actions
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 8.2 Write property test for playback speed interval
    - **Property 9: Playback speed interval correctness**
    - **Validates: Requirements 4.3, 4.4**

- [ ] 9. Implement scoreboard and event log
  - [x] 9.1 Create Scoreboard component (`src/components/Scoreboard.jsx`)
    - Display players sorted by current score descending
    - Show: strategy name, score, current node, termination status
    - Checkmark icon for finished players
    - Updates reactively when turn changes
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [ ]* 9.2 Write property tests for scoreboard
    - **Property 6: Scoreboard completeness and ordering**
    - **Validates: Requirements 5.1, 5.3, 5.4**

  - [x] 9.3 Create EventLog component (`src/components/EventLog.jsx`)
    - Scrollable panel showing all events
    - Format: turn number, model name, event type, details
    - Highlight events at or before current turn
    - Click event to jump Turn_Slider to that turn
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 9.4 Write property tests for event log
    - **Property 7: Event log completeness and formatting**
    - **Property 8: Event log turn filtering**
    - **Validates: Requirements 6.1, 6.2, 6.4**

- [ ] 10. Implement layout and player legend
  - [x] 10.1 Create PlayerLegend component and responsive layout (`src/components/PlayerLegend.jsx`, update `App.jsx`)
    - PlayerLegend: color swatch + strategy name for each player
    - Responsive layout: side-by-side at ≥768px, stacked vertically below
    - Graph_View takes primary space (60-70% width on desktop)
    - Wire all components together in GameVisualization container
    - _Requirements: 3.3, 8.1, 8.2, 8.3_

- [ ] 11. Implement event highlighting on graph
  - [x] 11.1 Add node highlight animation on turn advance
    - When turn changes and events exist at that turn, briefly pulse affected nodes
    - Use CSS animation or canvas highlight for 500ms
    - _Requirements: 4.6_

- [x] 12. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Property tests use fast-check with minimum 100 iterations
- The frontend has zero coupling to the Python backend — it only reads the JSON file format
