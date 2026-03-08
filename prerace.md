# Pre-Race Feature Plan

Two features that bring the app to life outside of a live race window: a dynamic driver/team
roster sourced from OpenF1, and a pre-race countdown that auto-connects when the race starts.

---

## Feature 1 — Dynamic Driver / Team Roster

### Goal

Replace the hardcoded `teamColors.ts` with live data from OpenF1. The frontend fetches driver
codes, team names, and team colours once on mount via the backend, and uses them everywhere
team colours are rendered.

### Data source

```
GET https://api.openf1.org/v1/drivers?session_key=latest
```

Returns (per driver):
```json
{
  "driver_number": 1,
  "name_acronym": "VER",
  "team_name": "Red Bull Racing",
  "team_colour": "3671C6"
}
```

### Backend changes

**`backend/app/openf1.py`**
- Extract the token-fetching logic out of `mqtt_worker.py` into a shared `get_token()` function
  in `openf1.py` so both the worker and the API routes can call it without duplicating code.
- Add `fetch_drivers_for_season(token: str) -> list[dict]` that calls
  `/v1/drivers?session_key=latest` and returns the raw list.

**`backend/app/routes.py`**
- Add `GET /api/drivers` endpoint.
- On first call: calls `get_token()` then `fetch_drivers_for_season()`, stores the result in a
  module-level dict (in-process cache), returns it.
- On subsequent calls: returns from the in-process cache without hitting OpenF1 again.
- Response shape: list of `{ driver_code, team_name, team_colour }` objects.

> Note: This is an in-process cache — each API replica fetches once independently. Acceptable
> for data that changes at most once per season.

### Frontend changes

**`frontend/src/App.tsx`**
- On mount (in a `useEffect`), `fetch('/api/drivers')`.
- Build a `Map<string, string>` keyed by `driver_code` → `#team_colour` (prepend `#` to the hex).
- Store in a `useState` — call it `driverColours`.
- Pass `driverColours` down as a prop to `Circuit` and `Leaderboard`.

**`frontend/src/components/circuit/index.tsx`**
- Accept `driverColours: Map<string, string>` as a prop.
- Replace the `TEAM_COLORS[team]` lookup with `driverColours.get(driver_code)`.
- The component already builds a `teamByDriver` map from leaderboard entries — this can be
  simplified by going directly driver_code → colour.

**`frontend/src/components/leaderboard/index.tsx`**
- Accept `driverColours: Map<string, string>` as a prop.
- Replace `TEAM_COLORS[entry.team]` with `driverColours.get(entry.driver_code)`.

**`frontend/src/teamColors.ts`**
- Kept as-is for dev mode (poller). No changes needed; it simply won't be used in premium mode.

---

## Feature 2 — Pre-Race Countdown + Dynamic Circuit

### Goal

When no race is happening, show a live countdown to the next race. When the countdown reaches
zero, automatically connect to the SSE stream. Once live, render the correct circuit based on
the session data arriving in the snapshot stream and display the race name in the leaderboard header.

### Sub-problem A — Next Race Schedule

#### Backend changes

**`backend/app/openf1.py`**
- Add `fetch_next_race(token: str) -> dict | None` that:
  - Calls `GET /v1/sessions?year=<current_year>&session_type=Race`
  - Filters to sessions where `date_start > now (UTC)`
  - Returns the earliest one: `{ circuit_short_name, date_start, session_name, session_key }`
  - Returns `None` if no future races found (end of season)

> Verify: check whether `/v1/sessions` requires a premium token or is publicly accessible.
> If public, `get_token()` can be skipped for this call. If not, use existing credentials.

**`backend/app/redis_store.py`**
- Add `get_schedule_cache() -> dict | None` — reads from key `static:schedule`.
- Add `set_schedule_cache(data: dict, ttl_seconds: int = 43200)` — writes with a 12-hour TTL.
  (12 hours is enough freshness; the schedule only changes if a race is postponed or cancelled.)

**`backend/app/routes.py`**
- Add `GET /api/schedule` endpoint:
  1. Check Redis for `static:schedule` — if present, return it.
  2. If cache miss: call `get_token()`, then `fetch_next_race()`, write to Redis cache, return.
  3. If no future races: return `null` (frontend handles end-of-season gracefully).
- Response shape:
  ```json
  {
    "circuit_short_name": "Sakhir",
    "date_start": "2026-03-20T15:00:00+00:00",
    "session_name": "Race",
    "session_key": 1234
  }
  ```

### Sub-problem B — Dynamic Circuit Rendering

#### Frontend changes

**`frontend/src/circuits.ts`** (or a new `frontend/src/circuitNameMap.ts`)
- Add a mapping constant translating OpenF1 `circuit_short_name` to `CircuitKey`:
  ```ts
  export const CIRCUIT_NAME_MAP: Record<string, CircuitKey> = {
    "Monte Carlo":  "monte_carlo",
    "Sakhir":       "sakhir",
    "Jeddah":       "jeddah",
    "Melbourne":    "melbourne",
    // ... all 22 circuits
  }
  ```
- This is the only hardcoded piece and it is correct by definition — circuit names do not
  change between seasons.

**`frontend/src/circuit-config.ts`**
- Remove (or leave in place for dev). `ACTIVE_CIRCUIT` is replaced by React state.

**`frontend/src/App.tsx`**
- Add `activeCircuit` state: `useState<CircuitKey | null>(null)`.
- Whenever a new snapshot arrives via SSE, derive the circuit:
  ```ts
  const key = CIRCUIT_NAME_MAP[snapshot.session?.circuit ?? ""]
  if (key) setActiveCircuit(key)
  ```
- Pass `activeCircuit` down to `Circuit` as a prop.

**`frontend/src/components/circuit/index.tsx`**
- Accept `activeCircuit: CircuitKey | null` as a prop instead of importing `ACTIVE_CIRCUIT`.
- Fall back to `"monte_carlo"` (or show nothing) if `activeCircuit` is null.

**`frontend/src/components/leaderboard/index.tsx`**
- The header currently hardcodes `"Race"`.
- Accept a `raceName: string` prop and render it as the title.
- `App.tsx` passes `snapshot.session?.circuit ?? "Race"` as `raceName`.

### Sub-problem C — Countdown UI + Auto-Connect

#### Frontend changes

**`frontend/src/App.tsx`**
- On mount, fetch `/api/schedule`.
- If response is non-null and `date_start > now`: store as `nextRace` state.
- Start a `setInterval` (every second) that computes the remaining time.
- When `Date.now() >= new Date(nextRace.date_start).getTime()`: call `setIsLive(true)` and
  clear the interval. This triggers the existing SSE `useEffect` automatically.

**New component: `frontend/src/components/countdown/index.tsx`**
- Accepts `targetDate: string` (ISO timestamp) and a `raceName: string`.
- Renders `DD HH:MM:SS` remaining with a label like `"Next Race: Sakhir"`.
- Shown in `App.tsx` when `nextRace !== null && !isLive`.

### The "Go Live" Button

- Stays exactly as-is. It is the manual trigger for dev/poller mode.
- Move it to a less prominent position (e.g., small button tucked to the side of the screen)
  so it does not confuse users in production but remains available for development.
- It still calls `setIsLive(true)` directly, bypassing the countdown entirely.

---

## Files Changed Summary

| File | Change |
|------|--------|
| `backend/app/openf1.py` | Extract `get_token()`, add `fetch_drivers_for_season()`, add `fetch_next_race()` |
| `backend/app/redis_store.py` | Add `get_schedule_cache()` / `set_schedule_cache()` |
| `backend/app/routes.py` | Add `GET /api/drivers`, add `GET /api/schedule` |
| `frontend/src/App.tsx` | Driver fetch on mount, schedule fetch on mount, countdown logic, auto-connect, activeCircuit state |
| `frontend/src/circuits.ts` | Add `CIRCUIT_NAME_MAP` constant |
| `frontend/src/circuit-config.ts` | Remove (replaced by state) |
| `frontend/src/components/circuit/index.tsx` | Accept `activeCircuit` + `driverColours` props |
| `frontend/src/components/leaderboard/index.tsx` | Accept `raceName` + `driverColours` props |
| `frontend/src/components/countdown/index.tsx` | New component |

---

## Implementation Order

1. **Backend first** — get `/api/drivers` and `/api/schedule` working and testable with `curl`
   before touching the frontend.
2. **Driver colours** — wire up `driverColours` in the frontend; verify team colours render
   correctly during a dev (poller) session.
3. **Countdown component** — build and style it in isolation with a hardcoded future date.
4. **Auto-connect** — wire the countdown to `setIsLive(true)` and verify the transition.
5. **Dynamic circuit** — wire `activeCircuit` from the snapshot stream; verify circuit switches
   correctly when a snapshot with a different `session.circuit` arrives.
