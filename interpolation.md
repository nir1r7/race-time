# Plan: Server-Side Cubic Spline Interpolation for Smooth Car Animation

## Context

MQTT delivers real snapshots at ~1 Hz with uneven timing (0.7s–1.3s between points). The
frontend animates each snapshot over a fixed 1s CSS transition, so cars appear to speed up or
slow down depending on the real data cadence — the animation is coupled to network jitter.

The fix is to decouple the two: keep MQTT writing raw snapshots to Redis unchanged, but add a
server-side interpolation layer inside the SSE generator that fits a cubic spline over the last
8 real snapshots and re-emits positions on a canonical fixed cadence of 250ms. The frontend
always receives evenly-spaced updates and only needs a fixed 250ms CSS transition.

Output stays strictly within the confirmed data window (never extrapolates) by maintaining a
1-snapshot lag behind the most recent real data.

---

## Files to Modify

| File | Change |
|---|---|
| `backend/requirements.txt` | Add `numpy>=1.26.0` |
| `backend/app/interpolator.py` | **New file** — all spline math |
| `backend/app/routes.py` | Rewrite `queue_generator()` |
| `frontend/src/App.tsx` | `INTERVAL_TIME`: 1000 → 250 |
| `frontend/src/static/styles/circuit.css` | CSS transition: `1.0s` → `0.25s` |

---

## Step 1 — `backend/requirements.txt`

Add after the `hiredis` line:
```
numpy>=1.26.0
```

---

## Step 2 — `backend/app/interpolator.py` (new file)

### Constants
```python
LAG = 1           # real snapshots to stay behind latest (guarantees no extrapolation)
WINDOW_SIZE = 8   # max real snapshots used for spline fitting
TRAIL_DEPTH = 6   # interpolated positions retained per driver as trail
MIN_SNAPSHOTS = LAG + 2   # = 3, minimum for a non-zero safe output range
```

### Timestamp helpers
- `_parse_unix_ts(ts: str) -> float` — normalise Z/+00:00 suffix, call `datetime.fromisoformat`, return `.timestamp()`
- `_unix_to_iso(t: float) -> str` — `datetime.fromtimestamp(t, tz=timezone.utc).isoformat()`

### Data structures

**`DriverSpline` dataclass:**
```
driver_number: int
driver_code: str
t_vals: np.ndarray   # shape (n,) – Unix timestamps, ascending
x_vals: np.ndarray   # shape (n,) – x_norm values
y_vals: np.ndarray   # shape (n,) – y_norm values
mx: np.ndarray       # shape (n,) – second derivatives for x spline
my: np.ndarray       # shape (n,) – second derivatives for y spline
n_points: int
```

**`FitResult` dataclass:**
```
splines: dict[int, DriverSpline]   # driver_number → DriverSpline
safe_start: float    # oldest window timestamp (Unix)
safe_end: float      # window[LAG].timestamp (Unix) — output must not exceed this
window: list[dict]   # raw window, index 0 = newest; used for leaderboard/session lookup
```

### `_fit_natural_cubic_spline(t, x) -> np.ndarray`

Returns second-derivative array `m` of shape `(n,)`.

```
1. h = np.diff(t)                          # interval widths
2. if n < 3: return np.zeros(n)            # constant (n=1) or linear (n=2) fallback
3. n_int = n - 2
4. main_diag = 2.0 * (h[:-1] + h[1:])    # shape (n_int,)
5. off_diag  = h[1:-1]                    # shape (n_int-1,)
6. d = 6.0 * ((x[2:]-x[1:-1])/h[1:] - (x[1:-1]-x[:-2])/h[:-1])
7. A = np.diag(main_diag) + np.diag(off_diag, 1) + np.diag(off_diag, -1)
8. m_interior = np.linalg.solve(A, d)
9. m = np.zeros(n); m[1:-1] = m_interior
10. return m
```

Natural boundary: `m[0] = m[-1] = 0`. Max matrix size is 6×6 (WINDOW_SIZE=8 → 6 interior knots) — negligible cost.

Before calling, deduplicate timestamps per driver: skip any observation whose `t <= last_seen_t`.

### `fit_splines(window: list[dict]) -> FitResult`

`window` is newest-first (Redis LRANGE order).

1. Iterate `reversed(window)` (oldest→newest). For each snapshot, for each position entry, accumulate `(unix_t, x_norm, y_norm)` per `driver_number` via a dict. Skip duplicate/non-advancing timestamps.
2. For each driver: build `t_arr, x_arr, y_arr` as numpy arrays. Compute `mx = _fit_natural_cubic_spline(t_arr, x_arr)`, same for `my`.
3. `safe_start = _parse_unix_ts(window[-1]["timestamp"])`
4. `safe_end   = _parse_unix_ts(window[LAG]["timestamp"])`
5. Return `FitResult`.

### `evaluate_spline(spline, t) -> tuple[float, float]`

```
1. Clamp t to [spline.t_vals[0], spline.t_vals[-1]]
2. i = np.searchsorted(spline.t_vals, t, side='right') - 1
   i = max(0, min(spline.n_points - 2, i))
3. h_i = t_vals[i+1] - t_vals[i]
   a = (t_vals[i+1] - t) / h_i
   b = (t - t_vals[i])   / h_i
4. For each coord (x, y):
   val = a*v[i] + b*v[i+1] + ((a³-a)*m[i] + (b³-b)*m[i+1]) * h_i² / 6
5. Clamp output to [0.0, 1.0] and round to 6 decimal places
```

### `interpolate_snapshot(fit, t, trail_state) -> dict`

`trail_state: dict[int, list]` mutated in place across calls (accumulates the trail).

1. Find `ref_snap`: scan `fit.window` from index 0 (newest); take first whose `parse_unix_ts <= t`. Fallback to `fit.window[-1]`.
2. For each driver in `fit.splines`: call `evaluate_spline`, append `[x, y]` to `trail_state[driver_number]`, trim to `TRAIL_DEPTH`. Build position dict with `trail = list(trail_state[driver_number])`.
3. Return:
```python
{
  "timestamp": _unix_to_iso(t),
  "positions": [...],
  "leaderboard": ref_snap.get("leaderboard", []),
  "session":     ref_snap.get("session", None),
}
```

---

## Step 3 — Rewrite `queue_generator()` in `backend/app/routes.py`

Add imports:
```python
from app.interpolator import (
    fit_splines, interpolate_snapshot,
    MIN_SNAPSHOTS, WINDOW_SIZE
)
```

### Local constants inside the generator
```python
QUEUE_DEPTH      = 15
OUTPUT_INTERVAL  = 0.25   # seconds
LAG              = 1
POLL_SLEEP       = 0.5
MAX_CATCHUP_S    = QUEUE_DEPTH * OUTPUT_INTERVAL   # 3.75s
```

### Phase 1 — Wait for minimum data
```python
while True:
    window = await redis_store.get_last_n_snapshots(WINDOW_SIZE)
    if len(window) >= MIN_SNAPSHOTS:
        break
    await asyncio.sleep(POLL_SLEEP)
```
SSE connection stays open; frontend shows "Buffering live data... 15".

### Phase 2 — Initial backfill (burst emit, no sleep)
```python
fit = fit_splines(window)
trail_state = {}

backfill_start = max(
    fit.safe_end - (QUEUE_DEPTH - 1) * OUTPUT_INTERVAL,
    fit.safe_start
)
t = backfill_start
while t <= fit.safe_end + 1e-9:
    snap = interpolate_snapshot(fit, t, trail_state)
    yield f"data: {json.dumps(snap)}\n\n"
    t += OUTPUT_INTERVAL

output_t       = fit.safe_end + OUTPUT_INTERVAL
last_seen_ts   = window[0]["timestamp"]
```
Up to 15 synthetic snapshots emitted immediately to pre-fill the frontend queue.

### Phase 3 — Main loop
```python
try:
    while True:
        await asyncio.sleep(OUTPUT_INTERVAL)

        # Check for new real snapshot
        latest = await redis_store.get_latest_snapshot()
        if latest and latest["timestamp"] != last_seen_ts:
            last_seen_ts = latest["timestamp"]
            new_window = await redis_store.get_last_n_snapshots(WINDOW_SIZE)
            if len(new_window) >= MIN_SNAPSHOTS:
                fit = fit_splines(new_window)
                # Skip ahead if output_t fell too far behind (e.g. after a stall)
                if fit.safe_end - output_t > MAX_CATCHUP_S:
                    output_t = fit.safe_end - MAX_CATCHUP_S

        # Stall gracefully when output has caught up to the safe boundary
        if output_t > fit.safe_end:
            continue

        snap = interpolate_snapshot(fit, output_t, trail_state)
        yield f"data: {json.dumps(snap)}\n\n"
        output_t += OUTPUT_INTERVAL

except asyncio.CancelledError:
    pass
```

**Stall behavior:** when `output_t > fit.safe_end` the generator does not yield; the frontend
queue drains and shows "Buffering" again. Self-resolves when new real data arrives and
`safe_end` advances.

**Catch-up guard:** if MQTT was stalled and `safe_end` jumps ahead by >3.75s, `output_t` is
snapped forward rather than fast-forwarding through seconds of history.

**Each client gets independent state** (`trail_state`, `output_t`, `fit`) — no shared mutable
state between SSE connections.

---

## Step 4 — `frontend/src/App.tsx`

Line 27, change:
```typescript
const INTERVAL_TIME = 1000;
```
to:
```typescript
const INTERVAL_TIME = 250;
```

`QUEUE_DEPTH` stays at 15 (= 3.75s buffer at new cadence).

---

## Step 5 — `frontend/src/static/styles/circuit.css`

Line 36, change:
```css
transition: left 1.0s linear, top 1.0s linear;
```
to:
```css
transition: left 0.25s linear, top 0.25s linear;
```

Comment on line 35 (`/* Duration must match INTERVAL_TIME in App.tsx */`) remains accurate.

---

## Edge Cases

| Scenario | Handling |
|---|---|
| Redis empty on connect | Phase 1 polls every 500ms until ≥3 snapshots exist |
| Driver with 1 point | n_points=1 → constant position returned; moves on next refit |
| Driver with 2 points | m=zeros → degenerates to linear interpolation |
| Driver missing some snapshots | Spline fitted on observed points only; gaps bridged smoothly |
| Duplicate timestamps in window | Deduplicated in `fit_splines` before fitting |
| MQTT stops (session end) | Stall: generator holds `output_t`, frontend shows "Buffering" |
| Long stall resolves | `output_t` snapped to `safe_end - 3.75s` to avoid fast-forward |
| < MIN_SNAPSHOTS after Redis clear | Old `fit` retained; stall condition triggers gracefully |
| h[i] = 0 after dedup fails | `np.linalg.solve` would produce NaN; dedup in `fit_splines` prevents this |

---

## Verification

1. Start stack: `docker-compose --profile dev up`
2. Open browser at `http://localhost:5173`, click "Go Live"
3. **Buffering phase**: confirm buffer countdown from 15 completes in ~4s (15 × 250ms) rather than ~15s
4. **Smooth motion**: driver dots should glide continuously — no 1-second jump pattern
5. **Network tab**: SSE messages should arrive at ~250ms intervals, not ~1s intervals
6. **Stale data**: pause the poller (`docker-compose stop poller`), confirm "Data stale" appears after 15s; restart poller, confirm recovery
7. **Multi-client**: open two browser tabs simultaneously; both should animate smoothly and independently
