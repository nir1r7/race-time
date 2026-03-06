import { useState, useEffect, useRef } from 'react'
import { Snapshot } from "./types.ts";
import Circuit from './components/circuit'
import Leaderboard from './components/leaderboard'
import './static/styles/app.css'


export default function App() {
  const [isLive, setIsLive] = useState<boolean>(false);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const INTERVAL_TIME = 505; // must match transition duration in circuit.css
  const MAX_QUEUE_DEPTH = 15;
  
  const snapshotQueue = useRef<Snapshot[]>([]);

  const isStale = snapshot !== null && Date.now() - new Date(snapshot.timestamp).getTime() > 5000;

  useEffect(() => {
    if (!isLive) {
      setSnapshot(null);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    const es = new EventSource("/api/live/stream")

    es.onopen = () => {
      setError(null);
    };

    es.onmessage = (event) => {
      const snapshot: Snapshot = JSON.parse(event.data);
      snapshotQueue.current.push(snapshot);

      if (snapshotQueue.current.length > MAX_QUEUE_DEPTH){
        snapshotQueue.current = snapshotQueue.current.slice(-MAX_QUEUE_DEPTH);
      }
    };

    es.onerror = () => {
      setError("Connection lost, reconnecting");
      setLoading(false);
    };

    const handleVisibilityChange = () => {
      if (!document.hidden) {
        snapshotQueue.current = snapshotQueue.current.slice(-5);
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    const displayInterval = setInterval(() => {
      if (snapshotQueue.current.length === 0) return;

      const next = snapshotQueue.current.shift()!;

      const now = new Date()
      console.log(
        `${now.toLocaleTimeString()}.${now.getMilliseconds()} + ${snapshotQueue.current.length}`
      )
      console.log(next);

      setSnapshot(next);
      setLoading(false);
      setError(null);
    }, INTERVAL_TIME);

    return () => {
      es.close();
      clearInterval(displayInterval);
      snapshotQueue.current = [];
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isLive]);

  return (
    <div className="app">
      <div className="app-controls">
        <button className="app-btn" onClick={() => setIsLive(!isLive)}>
          {isLive ? 'Stop' : 'Go Live'}
        </button>
        {isLive && error && <span className="app-status app-status--error">{error}</span>}
        {isLive && !error && loading  && <span className="app-status">Connecting...</span>}
        {isLive && !error && isStale  && <span className="app-status app-status--stale">Data stale</span>}
      </div>

      {isLive && !error && !loading && snapshot && (
        <div className="live-layout">
          <div className="live-layout__leaderboard">
            <Leaderboard entries={snapshot.leaderboard} />
          </div>
          <div className="live-layout__circuit">
            <Circuit positions={snapshot.positions} leaderboard={snapshot.leaderboard} />
          </div>
        </div>
      )}
    </div>
  )
}
