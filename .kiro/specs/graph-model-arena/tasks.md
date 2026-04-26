# Implementation Plan: Graph Model Arena

## Overview

Implement the Graph Model Arena in Python as a standalone package. Uses `dataclasses` for data models, `enum` for types, and `hypothesis` for property-based testing. The implementation follows the component architecture from the design: Graph Generator → Game Engine → Turn Manager → State Resolver → Model Strategies → Game Reporter.

## Tasks

- [ ] 1. Set up project structure, data models, and configuration validation
  - [x] 1.1 Create project directory structure and core enums/types
    - Create `graph_model_arena/` package with `__init__.py`
    - Create `graph_model_arena/models.py` with all data model dataclasses: `Node`, `Edge`, `Graph`, `GraphConfig`, `GameConfig`, `ModelState`, `GameState`, `GameEvent`, `GameSummary`, `RankedModel`, `ModelView`, `MoveResult`, `ValidatedMove`
    - Implement `NodeType` enum (NORMAL, START, END, TRAP, CLUE, MAP, CHECKPOINT, POINTS), `EventType` enum, `TerminationCause` enum (FINISHED, TURN_LIMIT)
    - _Requirements: 1.4, 2.1, 5.6, 7.5_

  - [x] 1.2 Implement configuration validation
    - Add validation methods to `GraphConfig` (num_nodes 20-200, probabilities 0-1, edge_density 0-1, map_reveal_depth 1-3)
    - Add validation methods to `GameConfig` (num_models 2-8, max_turns > 0, timeout > 0)
    - Raise `ValueError` with descriptive messages for invalid configs
    - _Requirements: 6.4, 7.1_

  - [x] 1.3 Write property test for model count bounds
    - **Property 23: Model count bounds**
    - **Validates: Requirements 6.4**

- [x] 2. Implement Graph Generator
  - [x] 2.1 Implement `graph_generator.py` with `generate_graph(config: GraphConfig) -> Graph`
    - Generate nodes and connect via random spanning tree for guaranteed connectivity
    - Add additional random edges based on edge_density
    - Designate start and end nodes (maximize distance)
    - Assign node types via weighted random selection (start/end nodes stay as START/END)
    - Assign edge costs randomly in [1, 10]
    - Place obstacles on non-bridge edges to preserve reachability
    - Verify trap-free path exists; if not, convert traps along one safe path to NORMAL
    - Retry logic with configurable max retries
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 2.2 Write property tests for Graph Generator (Properties 1-5)
    - **Property 1: Generated graphs are connected with correct node count**
    - **Property 2: Start and end nodes exist with a valid path**
    - **Property 3: A trap-free path exists from start to end**
    - **Property 4: All edge costs are in valid range**
    - **Property 5: Node types are validly assigned**
    - **Validates: Requirements 1.1, 1.2, 1.3, 1.4, 1.5, 1.6**

- [ ] 3. Implement Visibility Manager and Score Manager
  - [ ] 3.1 Implement `visibility_manager.py`
    - `initialize_visibility(model_id, graph, game_state) -> GameState` — set visibility to start node + neighbors
    - `expand_visibility(model_id, center_node, depth, game_state) -> GameState` — BFS expansion
    - `get_visible_graph(model_id, game_state) -> VisibleGraph` — filtered graph view
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [ ] 3.2 Implement `score_manager.py`
    - `apply_points(model_state, node) -> ModelState` — add points on first visit only
    - `apply_completion_bonus(model_state, turns_taken, max_turns, multiplier) -> ModelState`
    - `apply_death_penalty(model_state, penalty) -> ModelState` — for trap respawn at start
    - `apply_trap_respawn_penalty(model_state, penalty) -> ModelState` — for trap respawn at checkpoint
    - `apply_invalid_move_penalty(model_state, penalty) -> ModelState`
    - `compute_final_rankings(model_states) -> list[RankedModel]` — sort by score desc, ties by turns asc
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [ ]* 3.3 Write property test for points collection
    - **Property 11: Points collection — first visit vs. revisit**
    - **Validates: Requirements 2.6, 2.7, 5.2**

  - [ ]* 3.4 Write property test for final ranking correctness
    - **Property 20: Final ranking correctness**
    - **Validates: Requirements 5.5**

- [ ] 4. Implement Node Effect Processor and Move Validator
  - [ ] 4.1 Implement `node_effects.py` with `process_node_effect(model_state, node, game_state) -> ModelState`
    - Process effects in order: checkpoint activation, trap check, clue reveal, map reveal, points collection
    - Trap without checkpoint: respawn at Starting_Node, apply death_penalty, increment trap_deaths, log TRAP_RESPAWN_START event
    - Trap with checkpoint: respawn at checkpoint, apply trap_respawn_penalty, increment trap_deaths, log TRAP_RESPAWN_CHECKPOINT event
    - Clue: reveal one random neighbor's type to model only
    - Map: expand visibility by configured depth
    - Checkpoint: set active_checkpoint
    - Points: add points if first visit
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 2.7_

  - [ ] 4.2 Implement `move_validator.py` with `validate_move(model_id, target_node, game_state) -> MoveResult`
    - Check adjacency and edge obstruction
    - Return valid/invalid with reason
    - _Requirements: 4.2_

  - [ ]* 4.3 Write property tests for node effects (Properties 6-10)
    - **Property 6: Trap respawn at start without checkpoint**
    - **Property 7: Trap respawn with checkpoint**
    - **Property 8: Clue node reveals exactly one neighbor's type**
    - **Property 9: Map node expands visibility by configured depth**
    - **Property 10: Checkpoint activation**
    - **Validates: Requirements 2.1, 2.2, 2.3, 2.4, 2.5, 3.3, 3.4, 5.4**

  - [ ]* 4.4 Write property test for move validation
    - **Property 15: Move validation correctness**
    - **Validates: Requirements 4.2**

- [ ] 5. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Implement State Resolver and Turn Manager
  - [ ] 6.1 Implement `state_resolver.py` with `resolve_moves(moves, game_state) -> GameState`
    - Move models to target nodes simultaneously
    - Call node effect processor for each model's new node
    - Expand visibility for each model (depth 1 from new position)
    - Handle trap respawn repositioning (checkpoint or Starting_Node)
    - _Requirements: 4.4, 2.1, 2.2_

  - [ ] 6.2 Implement `turn_manager.py` with `execute_turn(game_state) -> GameState`
    - Collect moves from all active (non-finished) models with timeout
    - Validate each move via Move Validator
    - Apply invalid move penalty for bad moves
    - Handle timeout as no-op with no penalty
    - Handle model exceptions as no-op with no penalty (log error)
    - Pass validated moves to State Resolver
    - Increment turn counter
    - _Requirements: 4.1, 4.2, 4.3, 4.5, 4.6, 6.5_

  - [ ]* 6.3 Write property tests for turn mechanics (Properties 16-19)
    - **Property 16: Invalid move penalty**
    - **Property 17: Simultaneous move resolution is order-independent**
    - **Property 18: Completion bonus calculation**
    - **Property 19: Timeout results in no-op without penalty**
    - **Validates: Requirements 4.3, 4.4, 4.5, 4.6, 5.3**

- [ ] 7. Implement Game Engine and Game Reporter
  - [ ] 7.1 Implement `game_engine.py`
    - `create_game(config: GameConfig) -> Game` — validate config, generate graph, initialize model states at Starting_Node
    - `start_game(game: Game) -> GameResult` — run turn loop, check end conditions each turn
    - End conditions: all models finished, or max turns reached
    - On turn limit: score remaining models by proximity to Ending_Node (shortest path distance)
    - Record completion bonus when model reaches Ending_Node
    - _Requirements: 7.1, 7.2, 7.3, 7.4_

  - [ ] 7.2 Implement `game_reporter.py`
    - `generate_summary(game) -> GameSummary` — include full graph, rankings, graph_stats, event_log
    - `serialize_game(game) -> dict` — JSON-serializable dict with full graph, all moves, scores, events
    - `deserialize_game(data: dict) -> GameState` — reconstruct game state from serialized data
    - _Requirements: 5.6, 7.5_

  - [ ]* 7.3 Write property tests for game lifecycle and serialization (Properties 12, 21-26)
    - **Property 12: Initialization invariant**
    - **Property 21: Game summary completeness**
    - **Property 22: Unique model identifiers**
    - **Property 24: Game ends when all models have finished**
    - **Property 25: Turn limit ends game with proximity scoring**
    - **Property 26: Game state serialization round trip**
    - **Validates: Requirements 3.1, 5.1, 5.6, 6.3, 7.2, 7.3, 7.4, 7.5**

- [ ] 8. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 9. Implement Model Interface and 8 Built-in Strategies
  - [ ] 9.1 Implement `model_interface.py` with abstract `ModelStrategy` base class
    - Abstract method `decide_move(self, state: ModelView) -> str`
    - Model registration and unique ID assignment
    - _Requirements: 6.1, 6.2, 6.3_

  - [ ] 9.2 Implement 8 model strategies in `strategies/`
    - `random_walker.py` — Random_Walker: pick random adjacent node
    - `greedy_explorer.py` — Greedy_Explorer: prioritize unvisited, move toward highest-value Points_Node
    - `shortest_path.py` — Shortest_Path: Dijkstra on visible graph toward Ending_Node
    - `cautious_navigator.py` — Cautious_Navigator: avoid unknown nodes, prioritize Checkpoint_Nodes
    - `risk_taker.py` — Risk_Taker: explore aggressively, ignore trap risk, seek Points_Nodes
    - `clue_seeker.py` — Clue_Seeker: prioritize Clue_Nodes and Map_Nodes first
    - `sprint_runner.py` — Sprint_Runner: beeline to Ending_Node, ignore points
    - `balanced_strategist.py` — Balanced_Strategist: switch between explore/collect/goal-seek based on turn count and score
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8_

  - [ ]* 9.3 Write property test for model strategy validity
    - **Property 27: All model strategies produce valid moves**
    - **Validates: Requirements 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7, 8.8**

  - [ ]* 9.4 Write property tests for visibility (Properties 13-14)
    - **Property 13: Movement expands visibility**
    - **Property 14: ModelView accuracy**
    - **Validates: Requirements 3.2, 3.5, 6.1**

- [ ] 10. Wire everything together and integration test
  - [ ] 10.1 Create `main.py` entry point
    - Accept game configuration (CLI args or defaults)
    - Create game, register models, run game, print summary
    - Serialize final game state to JSON file
    - _Requirements: 7.1, 7.2, 7.5_

  - [ ]* 10.2 Write integration tests
    - Run a full game with minimum config (20 nodes, 2 models, low turns) and verify summary structure
    - Run a game where a model hits a trap without checkpoint and verify respawn at Starting_Node
    - Run a game where a model hits a trap with checkpoint and verify respawn at checkpoint
    - Run a game that hits turn limit and verify proximity scoring
    - _Requirements: 2.1, 2.2, 7.3, 7.4_

- [ ] 11. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Implementation language: Python (using `dataclasses`, `enum`, `hypothesis` for PBT, `pytest` for testing)
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
