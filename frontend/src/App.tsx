import { useState, useEffect } from 'react'
import { fetchLiveSnapshot } from "./api";
import Circuit from './components/circuit'
import Leaderboard from './components/leaderboard'
import './static/styles/app.css'

import { Snapshot } from "./types.ts";

export default function App() {
  const [isLive, setIsLive] = useState<boolean>(false);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);

  const isStale =
    snapshot !== null &&
    Date.now() - new Date(snapshot.timestamp).getTime() > 5000;

  useEffect(() => {
    if (!isLive) {
      setSnapshot(null);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);

    const id = setInterval(async () => {
      try {
        const data = await fetchLiveSnapshot();
        if (data) {
          setSnapshot(data);
          setLoading(false);
          setError(null);
        }
        // null return (503 — no snapshot yet) keeps loading state active
      } catch {
        setError("Failed to reach the API");
        setLoading(false);
      }
    }, 1000);

    return () => clearInterval(id);
  }, [isLive]);

  return (
    <>
      <h1>I'm the goat</h1>
      this is the start of something great
      <br />
      <button onClick={() => setIsLive(!isLive)}>{isLive ? 'Stop' : 'Live'}</button>

      {isLive && (
        <>
          {error && <p>Error: {error}</p>}
          {!error && loading && <p>Loading...</p>}
          {!error && isStale && <p>Warning: Data is stale (&gt;5s old)</p>}
          {!error && !loading && snapshot && (
            <div className="live-layout">
              <div className="live-layout__leaderboard">
                <Leaderboard entries={snapshot.leaderboard} />
              </div>
              <div className="live-layout__circuit">
                <Circuit positions={snapshot.positions} />
              </div>
            </div>
          )}
        </>
      )}
    </>
  )
}
