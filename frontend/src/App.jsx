import './App.css'
import { GameProvider, useGame } from './context/GameContext'
import { FileUploader } from './components/FileUploader'
import { GameSelector } from './components/GameSelector'
import { GraphCanvas } from './components/GraphCanvas'
import { PlaybackControls } from './components/PlaybackControls'
import { Scoreboard } from './components/Scoreboard'
import { EventLog } from './components/EventLog'
import { PlayerLegend } from './components/PlayerLegend'

function AppContent() {
  const { state, dispatch } = useGame()

  const handleBack = () => {
    dispatch({ type: 'LOAD_GAMES', payload: { games: state.games } })
  }

  return (
    <div className="App">
      <h1>Graph Model Arena - Visualizer</h1>

      {!state.selectedGame ? (
        <div className="upload-section">
          <FileUploader />
          {state.games.length > 0 && <GameSelector />}
        </div>
      ) : (
        <div className="visualization-section">
          <button className="back-btn" onClick={handleBack}>
            ← Back to game selection
          </button>
          <div className="game-visualization">
            <div className="main-panel">
              <GraphCanvas />
              <PlaybackControls />
            </div>
            <div className="side-panel">
              <Scoreboard />
              <EventLog />
              <PlayerLegend />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function App() {
  return (
    <GameProvider>
      <AppContent />
    </GameProvider>
  )
}

export default App
