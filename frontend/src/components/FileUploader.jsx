import { useState, useRef } from 'react';
import { useGame } from '../context/GameContext';
import { parseGameData } from '../utils/parseGameData';

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50MB

export function FileUploader() {
  const { dispatch } = useGame();
  const [error, setError] = useState(null);
  const fileInputRef = useRef(null);

  function handleFileChange(event) {
    const file = event.target.files[0];
    if (!file) return;

    setError(null);

    if (file.size > MAX_FILE_SIZE) {
      setError('File exceeds 50MB limit');
      return;
    }

    if (typeof FileReader === 'undefined') {
      setError('Your browser does not support file uploads');
      return;
    }

    const reader = new FileReader();

    reader.onload = (e) => {
      const text = e.target.result;
      const result = parseGameData(text);

      if (result.success) {
        dispatch({ type: 'LOAD_GAMES', payload: { games: result.games } });
        setError(null);
      } else {
        setError(result.error);
      }
    };

    reader.onerror = () => {
      setError('Failed to read file');
    };

    reader.readAsText(file);
  }

  return (
    <div className="file-uploader">
      <label htmlFor="game-file-input">Upload game results JSON:</label>
      <input
        id="game-file-input"
        ref={fileInputRef}
        type="file"
        accept=".json"
        onChange={handleFileChange}
        aria-describedby={error ? 'file-upload-error' : undefined}
      />
      {error && (
        <p id="file-upload-error" className="error-message" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}
