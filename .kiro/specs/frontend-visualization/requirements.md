# Requirements Document

## Introduction

A React-based frontend visualization UI for Graph Model Arena that renders completed game states as interactive graph visualizations. The frontend lives in a `frontend/` directory, consumes game result JSON data, and is fully optional — the Python backend continues to operate independently without it.

## Glossary

- **Frontend**: The React JavaScript application in the `frontend/` directory that visualizes game data
- **Backend**: The existing Python Graph Model Arena game engine in `graph_model_arena/`
- **Game_Result**: A JSON object produced by the backend containing full game state including graph, model states, events, rankings, and configuration
- **Graph_View**: The visual representation of nodes and edges rendered on a canvas
- **Node**: A vertex in the game graph with a type (START, END, NORMAL, TRAP, CLUE, MAP, CHECKPOINT, POINTS) and optional point value
- **Edge**: A connection between two nodes with a cost and an obstructed/unobstructed status
- **Model_Player**: An AI strategy competing in the game, represented visually on the graph
- **Event_Log**: The chronological list of game events (moves, traps, points collected, etc.)
- **Turn_Slider**: A UI control that allows the user to step through game turns
- **Scoreboard**: A panel showing current rankings and scores for all model players

## Requirements

### Requirement 1: Game Data Loading

**User Story:** As a user, I want to load game results into the frontend, so that I can visualize completed games.

#### Acceptance Criteria

1. WHEN the Frontend starts, THE Frontend SHALL display a file upload interface to accept a game results JSON file
2. WHEN a user uploads a valid game results JSON file, THE Frontend SHALL parse it and display a list of available games sorted by timestamp in descending order (most recent game first)
3. WHEN a user selects a game from the list, THE Frontend SHALL load the full game state for visualization
4. IF an uploaded file contains invalid JSON or missing required fields, THEN THE Frontend SHALL display a descriptive error message and allow re-upload
5. WHEN a game results file contains multiple games, THE Frontend SHALL allow the user to select which game to visualize

### Requirement 2: Graph Visualization

**User Story:** As a user, I want to see the game graph rendered visually, so that I can understand the structure of the game board.

#### Acceptance Criteria

1. WHEN a game is loaded, THE Graph_View SHALL render all nodes as circles with positions calculated via a force-directed layout
2. THE Graph_View SHALL color-code nodes by type: green for START, red for END, gray for NORMAL, orange for TRAP, blue for CLUE, purple for MAP, yellow for CHECKPOINT, gold for POINTS
3. WHEN a node has a point value greater than zero, THE Graph_View SHALL display the point value as a label inside the node
4. THE Graph_View SHALL render edges as lines connecting their source and target nodes
5. WHEN an edge is obstructed, THE Graph_View SHALL render it with a dashed line style
6. THE Graph_View SHALL display edge cost as a small label on each edge
7. WHEN the user hovers over a node, THE Graph_View SHALL display a tooltip showing the node ID and type

### Requirement 3: Player Position Display

**User Story:** As a user, I want to see where each model player is on the graph at any point in the game, so that I can track their progress.

#### Acceptance Criteria

1. WHEN a game is loaded, THE Frontend SHALL display each Model_Player as a distinct colored marker at their current node position
2. WHEN multiple Model_Players occupy the same node, THE Frontend SHALL offset their markers to avoid overlapping
3. THE Frontend SHALL display a legend mapping each Model_Player color to their strategy name

### Requirement 4: Turn-by-Turn Playback

**User Story:** As a user, I want to step through the game turn by turn, so that I can understand how the game unfolded.

#### Acceptance Criteria

1. WHEN a game is loaded, THE Turn_Slider SHALL initialize at turn 0 with maximum value equal to the total turns played
2. WHEN the user moves the Turn_Slider, THE Frontend SHALL update all player positions to reflect the game state at that turn
3. WHEN the user clicks a play button, THE Frontend SHALL auto-advance the Turn_Slider at the currently selected playback speed
4. THE Frontend SHALL provide playback speed options of 1x (one turn per second), 1.5x, 2x, 3x, and 4x
5. WHEN the user clicks a pause button, THE Frontend SHALL stop auto-advancing
6. WHEN the Turn_Slider advances to a turn where an event occurred, THE Frontend SHALL briefly highlight the affected node

### Requirement 5: Scoreboard Display

**User Story:** As a user, I want to see the current scores and rankings, so that I can follow the competition.

#### Acceptance Criteria

1. THE Scoreboard SHALL display all Model_Players sorted by current score descending
2. WHEN the Turn_Slider changes, THE Scoreboard SHALL update scores to reflect the state at that turn
3. THE Scoreboard SHALL display for each Model_Player: strategy name, current score, current node, and termination status
4. WHEN a Model_Player has finished the game, THE Scoreboard SHALL indicate their completion with a checkmark icon

### Requirement 6: Event Log Panel

**User Story:** As a user, I want to see what events happened during the game, so that I can understand the key moments.

#### Acceptance Criteria

1. THE Frontend SHALL display a scrollable Event_Log panel showing all game events
2. WHEN the Turn_Slider changes, THE Event_Log SHALL highlight events at or before the current turn
3. WHEN the user clicks an event in the Event_Log, THE Turn_Slider SHALL jump to that event's turn
4. THE Event_Log SHALL format each event with the turn number, model name, event type, and relevant details

### Requirement 7: Optional Integration

**User Story:** As a developer, I want the frontend to be completely optional, so that the Python backend continues to work independently.

#### Acceptance Criteria

1. THE Backend SHALL operate without modification when the Frontend is not installed or running
2. THE Frontend SHALL consume only the existing game_results.json file format without requiring backend changes
3. THE Frontend SHALL be contained entirely within a `frontend/` directory at the project root
4. THE Frontend SHALL have its own package.json with independent dependency management

### Requirement 8: Responsive Layout

**User Story:** As a user, I want the UI to be usable on different screen sizes, so that I can use it on various monitors.

#### Acceptance Criteria

1. THE Frontend SHALL arrange the Graph_View, Scoreboard, and Event_Log in a responsive layout
2. WHILE the viewport width is below 768px, THE Frontend SHALL stack panels vertically
3. WHILE the viewport width is 768px or above, THE Frontend SHALL display panels side by side with the Graph_View taking primary space
