# Requirements Document

## Introduction

Graph Model Arena is a competitive AI playground where 4-8 AI models compete simultaneously on a dynamically generated graph. Each model navigates from a fixed starting node to an ending node, encountering obstacles, traps, clues, map reveals, and checkpoints along the way. The goal is to reach the end with the maximum score. The graph topology, node properties, and obstacle placement change every game, ensuring no two competitions are alike.

## Glossary

- **Arena**: The complete game instance including the graph, competing models, and game state
- **Graph**: A collection of nodes connected by edges forming the playground
- **Node**: A vertex in the graph that may have special properties (checkpoint, trap, clue, map, points)
- **Edge**: A connection between two nodes; edges may have weights or traversal costs
- **Model**: An AI agent competing in the arena, making navigation decisions each turn
- **Turn**: A discrete time step in which each model selects and executes one move
- **Starting_Node**: The fixed node where all models begin the game
- **Ending_Node**: The target node that models must reach to finish the game
- **Trap_Node**: A node that eliminates a model from the game upon entry
- **Clue_Node**: A node that reveals partial information about the graph to the visiting model
- **Map_Node**: A node that reveals the graph structure up to a configurable neighbor depth for the visiting model
- **Checkpoint_Node**: A node that saves a model's progress, allowing respawn at the checkpoint instead of the start upon elimination
- **Points_Node**: A node that awards score points to the visiting model
- **Obstacle**: A blocked edge or node that prevents traversal
- **Visibility**: The portion of the graph a model can currently perceive
- **Game_Engine**: The core system that manages graph generation, turn execution, scoring, and game state
- **Graph_Generator**: The component responsible for creating randomized graph topologies and assigning node properties

## Requirements

### Requirement 1: Graph Generation

**User Story:** As a game operator, I want dynamically generated graphs for each game, so that every competition is unique and models cannot memorize paths.

#### Acceptance Criteria

1. WHEN a new game is initialized, THE Graph_Generator SHALL produce a connected graph with a configurable number of nodes (minimum 20, maximum 200)
2. WHEN generating a graph, THE Graph_Generator SHALL assign exactly one Starting_Node and exactly one Ending_Node such that at least one valid path exists between them
3. WHEN generating a graph, THE Graph_Generator SHALL ensure that a path from Starting_Node to Ending_Node exists that avoids all Trap_Nodes
4. WHEN generating a graph, THE Graph_Generator SHALL randomly assign node properties (Trap_Node, Clue_Node, Map_Node, Checkpoint_Node, Points_Node) according to configurable probability distributions
5. WHEN generating a graph, THE Graph_Generator SHALL place obstacles on edges according to a configurable density parameter, without making the Ending_Node unreachable from the Starting_Node
6. WHEN generating edges, THE Graph_Generator SHALL assign each edge a positive integer traversal cost between 1 and 10

### Requirement 2: Node Properties

**User Story:** As a game designer, I want nodes with diverse special properties, so that models face varied strategic decisions during navigation.

#### Acceptance Criteria

1. WHEN a model enters a Trap_Node, THE Game_Engine SHALL eliminate that model from the game unless the model has an active checkpoint
2. WHEN a model enters a Trap_Node and has an active checkpoint, THE Game_Engine SHALL respawn the model at the most recent Checkpoint_Node and deduct a configurable point penalty
3. WHEN a model enters a Clue_Node, THE Game_Engine SHALL reveal information about one randomly selected neighboring node's type to that model only
4. WHEN a model enters a Map_Node, THE Game_Engine SHALL reveal the graph structure within a configurable depth (1-3 edges) from the Map_Node to that model only
5. WHEN a model enters a Checkpoint_Node, THE Game_Engine SHALL record that checkpoint as the model's active respawn point
6. WHEN a model enters a Points_Node for the first time, THE Game_Engine SHALL add the node's point value to the model's score
7. WHEN a model enters a Points_Node that has already been visited by that model, THE Game_Engine SHALL award zero additional points

### Requirement 3: Model Visibility and Information

**User Story:** As a model developer, I want models to have limited but expandable visibility of the graph, so that exploration and information gathering are strategic elements.

#### Acceptance Criteria

1. WHEN a game starts, THE Game_Engine SHALL provide each model with visibility of only the Starting_Node and its immediate neighbors
2. WHEN a model moves to a new node, THE Game_Engine SHALL reveal that node and its immediate neighbors to that model
3. WHEN a model visits a Map_Node, THE Game_Engine SHALL expand that model's visibility by the configured depth from the Map_Node
4. THE Game_Engine SHALL maintain separate visibility states for each model, ensuring no model can access another model's discovered information
5. WHEN providing node information to a model, THE Game_Engine SHALL include the node type only for nodes within that model's visibility

### Requirement 4: Turn-Based Gameplay

**User Story:** As a game operator, I want structured turn-based gameplay, so that all models have equal opportunity to act each round.

#### Acceptance Criteria

1. WHEN a turn begins, THE Game_Engine SHALL request a move decision from each active (non-eliminated) model simultaneously
2. WHEN a model submits a move, THE Game_Engine SHALL validate that the target node is adjacent to the model's current position and the connecting edge is not obstructed by an obstacle
3. IF a model submits an invalid move, THEN THE Game_Engine SHALL keep the model at its current position and deduct one point as a penalty
4. WHEN all active models have submitted moves for a turn, THE Game_Engine SHALL resolve all moves simultaneously and update game state
5. WHEN a model reaches the Ending_Node, THE Game_Engine SHALL record the model's final score including a completion bonus inversely proportional to the number of turns taken
6. IF a model fails to submit a move within a configurable timeout period, THEN THE Game_Engine SHALL treat the move as a no-op with no penalty

### Requirement 5: Scoring System

**User Story:** As a game operator, I want a comprehensive scoring system, so that models are ranked by both speed and strategic play.

#### Acceptance Criteria

1. THE Game_Engine SHALL initialize each model's score to zero at the start of a game
2. WHEN a model collects points from a Points_Node, THE Game_Engine SHALL add the node's configured point value (1-10) to the model's score
3. WHEN a model reaches the Ending_Node, THE Game_Engine SHALL award a completion bonus calculated as: max_turns minus turns_taken, multiplied by a configurable bonus multiplier
4. WHEN a model is eliminated by a Trap_Node without a checkpoint, THE Game_Engine SHALL record the model's final score as the score at time of elimination minus a configurable death penalty
5. WHEN a game ends, THE Game_Engine SHALL rank all models by final score in descending order, with ties broken by fewer turns taken
6. WHEN a game ends, THE Game_Engine SHALL produce a game summary containing each model's final score, rank, path taken, nodes visited, and cause of termination

### Requirement 6: Model Interface

**User Story:** As a model developer, I want a clear interface for AI models, so that different strategies can be implemented and compete fairly.

#### Acceptance Criteria

1. THE Game_Engine SHALL provide each model with a standardized input containing: current node, visible graph subset, current score, turn number, and active checkpoint status
2. THE Game_Engine SHALL accept from each model a single output: the identifier of the target node to move to
3. WHEN a model is initialized, THE Game_Engine SHALL assign the model a unique identifier and register its strategy implementation
4. THE Game_Engine SHALL support between 2 and 8 models competing in a single game
5. IF a model raises an unhandled exception during move computation, THEN THE Game_Engine SHALL treat the move as a no-op and log the error

### Requirement 7: Game Lifecycle

**User Story:** As a game operator, I want clear game lifecycle management, so that games can be configured, run, and results collected reliably.

#### Acceptance Criteria

1. WHEN a game is created, THE Game_Engine SHALL accept a configuration specifying: number of nodes, edge density, node property probabilities, number of models, max turns, and timeout per move
2. WHEN a game is started, THE Game_Engine SHALL generate the graph, place all models at the Starting_Node, and begin turn processing
3. WHEN all active models have either reached the Ending_Node or been eliminated, THE Game_Engine SHALL end the game
4. IF the maximum turn limit is reached, THEN THE Game_Engine SHALL end the game and score remaining active models based on their proximity to the Ending_Node
5. WHEN a game ends, THE Game_Engine SHALL serialize the complete game state (graph, all moves, all scores, all events) to a structured format for future analysis

### Requirement 8: Initial Model Strategies

**User Story:** As a game operator, I want 8 pre-built model strategies, so that the arena can host competitions immediately.

#### Acceptance Criteria

1. THE Game_Engine SHALL include a Random_Walker model that selects a random adjacent node each turn
2. THE Game_Engine SHALL include a Greedy_Explorer model that prioritizes unvisited nodes and moves toward the highest-value visible Points_Node
3. THE Game_Engine SHALL include a Shortest_Path model that computes the shortest known path to the Ending_Node using only visible graph information
4. THE Game_Engine SHALL include a Cautious_Navigator model that avoids unknown nodes when possible and prioritizes Checkpoint_Nodes
5. THE Game_Engine SHALL include a Risk_Taker model that explores aggressively, ignoring potential traps in favor of discovering Points_Nodes
6. THE Game_Engine SHALL include a Clue_Seeker model that prioritizes visiting Clue_Nodes and Map_Nodes to maximize information before navigating to the Ending_Node
7. THE Game_Engine SHALL include a Sprint_Runner model that moves toward the Ending_Node as fast as possible, ignoring points collection
8. THE Game_Engine SHALL include a Balanced_Strategist model that dynamically switches between exploration, point collection, and goal-seeking based on turn count and score
