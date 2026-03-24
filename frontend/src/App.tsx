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
  const [isBuffering, setIsBuffering] = useState<boolean>(false);
  const [driverColours, setDriverColours] = useState<Map<string, string>>(new Map());
  const [nextRace, setNextRace] = useState<{ circuit_short_name: string; date_start: string; session_name: string; is_live: boolean } | null>(null);
  const [activeCircuit, setActiveCircuit] = useState<CircuitKey | null>(null);
  const [now, setNow] = useState<number>(() => Date.now());
  const [bufferCount, setBufferCount] = useState<number>(15);

  const snapshotQueue = useRef<Snapshot[]>([]);

  const isStale = snapshot !== null && now - new Date(snapshot.timestamp).getTime() > 15000;

  const INTERVAL_TIME = 250;
  const QUEUE_DEPTH = 15;
  const GAIN = 2;     // ms per item deviation from target depth
  const MIN_MS = 220;
  const MAX_MS = 280;

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
    snapshotQueue.current = [];
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

  // Tick every second so isStale and Countdown stay accurate
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  // Auto-start when the scheduled race time arrives
  useEffect(() => {
    if (!nextRace || isLive) return;
    if (now >= new Date(nextRace.date_start).getTime()) {
      setIsLive(true);
    }
  }, [now, nextRace, isLive]);

  useEffect(() => {
    if (!isLive) {
      setSnapshot(null);
      setLoading(false);
      setError(null);
      return;
    }

    setLoading(true);
    setError(null);
    setIsBuffering(true);
    setBufferCount(QUEUE_DEPTH);

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
      setBufferCount(prev => Math.max(0, prev - 1));

      // dont delete the line below at all costs
      console.log("len:", snapshotQueue.current.length, snapshotQueue.current);

      if (snapshotQueue.current.length > QUEUE_DEPTH + 5){
        snapshotQueue.current = snapshotQueue.current.slice(-(QUEUE_DEPTH + 5));
      }
    };

    es.onerror = () => {
      setError("Connection lost, reconnecting");
      setLoading(false);
    };

    const handleVisibilityChange = () => {
      if (!document.hidden) {
        snapshotQueue.current = snapshotQueue.current.slice(-15);
      }
    };

    document.addEventListener("visibilitychange", handleVisibilityChange);

    let hasStarted = false;
    let displayTimer: ReturnType<typeof setTimeout>;

    const consume = () => {
      if (snapshotQueue.current.length > 0) {
        if (!hasStarted && snapshotQueue.current.length < QUEUE_DEPTH) {
          displayTimer = setTimeout(consume, INTERVAL_TIME);
          return;
        }
        hasStarted = true;
        const next = snapshotQueue.current.shift()!;
        setIsBuffering(false);
        setSnapshot(next);
        setLoading(false);
        setError(null);
      }
      const error = snapshotQueue.current.length - QUEUE_DEPTH;
      const nextDelay = Math.max(MIN_MS, Math.min(MAX_MS, INTERVAL_TIME - GAIN * error));
      displayTimer = setTimeout(consume, nextDelay);
    };

    displayTimer = setTimeout(consume, INTERVAL_TIME);

    return () => {
      es.close();
      clearTimeout(displayTimer);
      snapshotQueue.current = [];
      setIsBuffering(false);
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
        {isLive && !error && isBuffering  && <span className="app-status">Buffering live data... {bufferCount}</span>}
        {isLive && !error && isStale  && <span className="app-status app-status--stale">Data stale</span>}
      </div>

      {!isLive && nextRace && (
        <Countdown targetDate={nextRace.date_start} raceName={nextRace.circuit_short_name} now={now} />
      )}

      {isLive && !error && !loading && snapshot && (
        <div className="live-layout">
          <div className="live-layout__leaderboard">
            <Leaderboard entries={snapshot.leaderboard} driverColours={driverColours} raceName={snapshot.session?.circuit ?? "Race"}/>
          </div>
          <div className="live-layout__circuit">
            <Circuit positions={snapshot.positions} driverColours={driverColours} activeCircuit={activeCircuit}/>
          </div>
        </div>
      )}
    </div>
  )
}
