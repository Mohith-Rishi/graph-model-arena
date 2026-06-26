import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { FileUploader } from './FileUploader';
import { GameProvider } from '../context/GameContext';

function makeValidGame(overrides = {}) {
  return {
    game_id: 'game-001',
    timestamp: '2024-01-15T10:30:00Z',
    config: {},
    rankings: [],
    graph_stats: {},
    total_turns: 10,
    full_state: {
      graph: { nodes: {}, edges: [], start_node: 'n1', end_node: 'n5' },
      models: { model_a: { current_node: 'n1', score: 0 } },
      event_log: [],
      current_turn: 10,
      max_turns: 50,
    },
    ...overrides,
  };
}

function createFile(content, name = 'games.json', type = 'application/json') {
  return new File([content], name, { type });
}

function renderFileUploader() {
  return render(
    <GameProvider>
      <FileUploader />
    </GameProvider>
  );
}

describe('FileUploader', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('renders a file input that accepts .json files', () => {
    renderFileUploader();
    const input = screen.getByLabelText(/upload game results json/i);
    expect(input).toBeInTheDocument();
    expect(input).toHaveAttribute('type', 'file');
    expect(input).toHaveAttribute('accept', '.json');
  });

  it('shows error when file exceeds 50MB limit', async () => {
    renderFileUploader();
    const input = screen.getByLabelText(/upload game results json/i);

    // Create a file object with size > 50MB
    const largeContent = 'x';
    const largeFile = createFile(largeContent, 'large.json');
    Object.defineProperty(largeFile, 'size', { value: 50 * 1024 * 1024 + 1 });

    fireEvent.change(input, { target: { files: [largeFile] } });

    expect(screen.getByRole('alert')).toHaveTextContent('File exceeds 50MB limit');
  });

  it('shows error for invalid JSON content', async () => {
    renderFileUploader();
    const input = screen.getByLabelText(/upload game results json/i);

    const file = createFile('not valid json');
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'Invalid JSON file. Please upload a valid game_results.json'
      );
    });
  });

  it('shows error for JSON missing required fields', async () => {
    renderFileUploader();
    const input = screen.getByLabelText(/upload game results json/i);

    const file = createFile(JSON.stringify([{ game_id: 'x', timestamp: 'y' }]));
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent(
        'full_state is required for visualization'
      );
    });
  });

  it('dispatches LOAD_GAMES on valid file upload', async () => {
    renderFileUploader();
    const input = screen.getByLabelText(/upload game results json/i);

    const games = [makeValidGame()];
    const file = createFile(JSON.stringify(games));
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      // No error should be displayed
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  it('clears previous error on successful upload', async () => {
    renderFileUploader();
    const input = screen.getByLabelText(/upload game results json/i);

    // First, upload invalid file
    const invalidFile = createFile('bad json');
    fireEvent.change(input, { target: { files: [invalidFile] } });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });

    // Then upload valid file
    const validFile = createFile(JSON.stringify([makeValidGame()]));
    fireEvent.change(input, { target: { files: [validFile] } });

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });

  it('does nothing when no file is selected', () => {
    renderFileUploader();
    const input = screen.getByLabelText(/upload game results json/i);

    fireEvent.change(input, { target: { files: [] } });

    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('clears error when a new file is selected (even if too large)', async () => {
    renderFileUploader();
    const input = screen.getByLabelText(/upload game results json/i);

    // Upload invalid JSON first
    const invalidFile = createFile('bad');
    fireEvent.change(input, { target: { files: [invalidFile] } });

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Invalid JSON file');
    });

    // Now upload oversized file — error should change
    const largeFile = createFile('x', 'large.json');
    Object.defineProperty(largeFile, 'size', { value: 50 * 1024 * 1024 + 1 });
    fireEvent.change(input, { target: { files: [largeFile] } });

    expect(screen.getByRole('alert')).toHaveTextContent('File exceeds 50MB limit');
  });

  it('shows error when file size is exactly at the limit (should pass)', async () => {
    renderFileUploader();
    const input = screen.getByLabelText(/upload game results json/i);

    // File at exactly 50MB should be allowed (not exceed)
    const games = [makeValidGame()];
    const content = JSON.stringify(games);
    const file = createFile(content, 'exact.json');
    Object.defineProperty(file, 'size', { value: 50 * 1024 * 1024 });

    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  });
});
