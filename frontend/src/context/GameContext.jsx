import { createContext, useContext, useReducer } from 'react';
import { computeTurnSnapshots } from '../utils/computeTurnSnapshots';

const GameContext = createContext(null);

const initialState = {
  games: [],
  selectedGame: null,
  turnSnapshots: [],
  currentTurn: 0,
  speed: 1,
  playing: false,
};

function gameReducer(state, action) {
  switch (action.type) {
    case 'LOAD_GAMES':
      return {
        ...initialState,
        games: action.payload.games,
      };

    case 'SELECT_GAME': {
      const game = action.payload;
      const turnSnapshots = computeTurnSnapshots(game.full_state);
      return {
        ...state,
        selectedGame: game,
        turnSnapshots,
        currentTurn: 0,
        playing: false,
      };
    }

    case 'SET_TURN': {
      const maxTurn = state.turnSnapshots.length > 0
        ? state.turnSnapshots.length - 1
        : 0;
      const clamped = Math.max(0, Math.min(action.payload, maxTurn));
      return {
        ...state,
        currentTurn: clamped,
      };
    }

    case 'SET_SPEED':
      return {
        ...state,
        speed: action.payload,
      };

    case 'TOGGLE_PLAY':
      return {
        ...state,
        playing: !state.playing,
      };

    default:
      return state;
  }
}

export function GameProvider({ children }) {
  const [state, dispatch] = useReducer(gameReducer, initialState);

  return (
    <GameContext.Provider value={{ state, dispatch }}>
      {children}
    </GameContext.Provider>
  );
}

export function useGame() {
  const context = useContext(GameContext);
  if (!context) {
    throw new Error('useGame must be used within a GameProvider');
  }
  return context;
}
