import { useEffect, useRef } from 'react';
import { useGame } from '../context/GameContext';

export function computeInterval(speed) {
  return 1000 / speed;
}

const SPEED_OPTIONS = [1, 1.5, 2, 3, 4];

export function PlaybackControls() {
  const { state, dispatch } = useGame();
  const { turnSnapshots, currentTurn, speed, playing } = state;
  const intervalRef = useRef(null);

  const maxTurn = turnSnapshots.length > 0 ? turnSnapshots.length - 1 : 0;

  // Keep refs in sync so the interval callback always has fresh values
  const turnRef = useRef(currentTurn);
  const maxTurnRef = useRef(maxTurn);

  useEffect(() => {
    turnRef.current = currentTurn;
  }, [currentTurn]);

  useEffect(() => {
    maxTurnRef.current = maxTurn;
  }, [maxTurn]);

  // Auto-advance interval
  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (playing) {
      const ms = computeInterval(speed);
      intervalRef.current = setInterval(() => {
        const nextTurn = turnRef.current + 1;
        if (nextTurn > maxTurnRef.current) {
          dispatch({ type: 'TOGGLE_PLAY' });
        } else {
          dispatch({ type: 'SET_TURN', payload: nextTurn });
        }
      }, ms);
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [playing, speed, dispatch]);

  const handleSliderChange = (e) => {
    dispatch({ type: 'SET_TURN', payload: Number(e.target.value) });
  };

  const handleTogglePlay = () => {
    dispatch({ type: 'TOGGLE_PLAY' });
  };

  const handleSpeedChange = (speedValue) => {
    dispatch({ type: 'SET_SPEED', payload: speedValue });
  };

  return (
    <div className="playback-controls">
      <div className="turn-slider">
        <label htmlFor="turn-slider">
          Turn: {currentTurn} / {maxTurn}
        </label>
        <input
          id="turn-slider"
          type="range"
          min={0}
          max={maxTurn}
          value={currentTurn}
          onChange={handleSliderChange}
        />
      </div>

      <button
        className="play-pause-btn"
        onClick={handleTogglePlay}
      >
        {playing ? 'Pause' : 'Play'}
      </button>

      <div className="speed-selector" role="group" aria-label="Playback speed">
        {SPEED_OPTIONS.map((opt) => (
          <button
            key={opt}
            className={speed === opt ? 'speed-btn active' : 'speed-btn'}
            onClick={() => handleSpeedChange(opt)}
            aria-pressed={speed === opt}
          >
            {opt}x
          </button>
        ))}
      </div>
    </div>
  );
}
