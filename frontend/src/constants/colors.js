/**
 * Color constants for Graph Model Arena visualization.
 * Node colors map to game node types, player colors are assigned
 * sequentially to model players on game load.
 */

export const NODE_COLORS = {
  START: '#4CAF50',       // green
  END: '#F44336',         // red
  NORMAL: '#9E9E9E',     // gray
  TRAP: '#FF9800',       // orange
  CLUE: '#2196F3',       // blue
  MAP: '#9C27B0',        // purple
  CHECKPOINT: '#FFEB3B', // yellow
  POINTS: '#FFD700'      // gold
};

export const PLAYER_COLORS = [
  '#E91E63', '#00BCD4', '#8BC34A', '#FF5722',
  '#673AB7', '#009688', '#CDDC39', '#795548'
];
