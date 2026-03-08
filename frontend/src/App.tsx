import { useState, useEffect, useRef } from 'react'
import { Snapshot } from "./types.ts";
import { CircuitKey } from './circuits.ts';
import { CIRCUIT_NAME_MAP } from './circuits.ts';
import Circuit from './components/circuit'
import Leaderboard from './components/leaderboard'
import Countdown from './components/countdown'
import './static/styles/app.css'


export default function App() {
  const [isLive, setIsLive] = useState<boolean>(false);
  const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [driverColours, setDriverColours] = useState<Map<string, string>>(new Map());
  const [nextRace, setNextRace] = useState<{ circuit_short_name: string; date_start: string; session_name: string; is_live: boolean } | null>(null);
  const [activeCircuit, setActiveCircuit] = useState<CircuitKey | null>(null);
  const [countdown, setCountdown] = useState<number>(0); // ms remaining

  const snapshotQueue = useRef<Snapshot[]>([]);

  const isStale = snapshot !== null && Date.now() - new Date(snapshot.timestamp).getTime() > 5000;

  const INTERVAL_TIME = 1000;
  const MAX_QUEUE_DEPTH = 15;

  useEffect(() => {
    fetch('/api/drivers')
      .then(response => response.json())
      .then((data: {driver_code: string; team_colour: string}[]) => {
        const map = new Map(data.map(d => [d.driver_code, `#${d.team_colour}`]));
        setDriverColours(map)
      })
      .catch(() => {})
  }, [])

  useEffect(() => {
    fetch('/api/schedule')
    .then(res => res.json())
    .then((data) => {
      if (!data) return;
      setNextRace(data);
      if (data.is_live) {
        setIsLive(true);
      }
    })
    .catch(() => {});
  }, [])

  useEffect(() => {
    if (!nextRace || isLive) return;

    const tick = () => {
      const remaining = new Date(nextRace.date_start).getTime() - Date.now() ;
      if (remaining <= 0){
        setIsLive(true)
        return;
      }
      setCountdown(remaining)
    };

    tick();
    const id = setInterval(tick, 1000);
    return () => clearInterval(id);
  }, [nextRace, isLive]);

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

      const circuitName = snapshot.session?.circuit ?? "";
      const key = CIRCUIT_NAME_MAP[circuitName];
      if (key) setActiveCircuit(key);

      snapshotQueue.current.push(snapshot);

      // dont delete the line below at all costs
      console.log("Queue length (after push):", snapshotQueue.current.length);


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

        setSnapshot(next);
        setLoading(false);
        setError(null);
    }, INTERVAL_TIME);
      
    return () => {
      es.close();
      clearInterval(displayInterval)
      snapshotQueue.current = [];
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, [isLive]);

  return (
    <div className="app">
      <div className="app-controls">
        <button className="app-btn app-btn--dev" onClick={() => setIsLive(!isLive)}>
          {isLive ? 'Stop' : 'Go Live'}
        </button>
        {isLive && error && <span className="app-status app-status--error">{error}</span>}
        {isLive && !error && loading  && <span className="app-status">Connecting...</span>}
        {isLive && !error && isStale  && <span className="app-status app-status--stale">Data stale</span>}
      </div>

      {!isLive && nextRace && (
        <Countdown targetDate={nextRace.date_start} raceName={nextRace.circuit_short_name} />
      )}

      {isLive && !error && !loading && snapshot && (
        <div className="live-layout">
          <div className="live-layout__leaderboard">
            <Leaderboard entries={snapshot.leaderboard} driverColours={driverColours} raceName={snapshot.session?.circuit ?? "Race"}/>
          </div>
          <div className="live-layout__circuit">
            <Circuit positions={snapshot.positions} leaderboard={snapshot.leaderboard} driverColours={driverColours} activeCircuit={activeCircuit}/>
          </div>
        </div>
      )}
    </div>
  )
}
