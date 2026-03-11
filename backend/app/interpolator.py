from datetime import datetime, timezone
from dataclasses import dataclass, field
import numpy as np
import json

LAG = 1
WINDOW_SIZE = 8
TRAIL_DEPTH = 6
MIN_SNAPSHOTS = LAG + 3


@dataclass
class DriverSpline:
    driver_number: int
    driver_code: str
    t_vals: np.ndarray
    x_vals: np.ndarray
    y_vals: np.ndarray
    mx: np.ndarray
    my: np.ndarray
    n_points: int

@dataclass
class FitResult:
    splines: dict
    safe_start: float
    safe_end: float
    window: list


def _parse_unix_ts(ts: str) -> float:
    normalized = ts.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).timestamp()


def _unix_to_iso(t: float) -> str:
    return datetime.fromtimestamp(t, tz=timezone.utc).isoformat()


def _fit_natural_cubic_spline(t: np.ndarray, x: np.ndarray) -> np.ndarray:
    n = len(t)

    # not enough points
    if n < 3:
        return np.zeros(n)
    
    # h[i] = t[i+1] - t[i]
    h = np.diff(t)

    # number of interior unkonwn 2nd derivatives
    n_int = n - 2

    # tridiagonal matrix entires
    main_diag = 2.0 * (h[:-1] + h[1:])
    off_diag = h[1:-1]

    # build right-hand side
    d = 6.0 * ((x[2:] - x[1:-1])/h[1:] - (x[1:-1] - x[:-2])/h[:-1])

    # assemble matrix
    A = np.diag(main_diag) + np.diag(off_diag, k=1) + np.diag(off_diag, k=-1)

    # solve lin system
    m_interior = np.linalg.solve(A, d)

    # assemble full array
    m = np.zeros(n)
    m[1:-1] = m_interior
    
    return m


def evaluate_spline(spline: DriverSpline, t: float) -> tuple[float, float]:
    # Clamp t to the driver's known data range
    t = max(spline.t_vals[0], min(spline.t_vals[-1], t))

    # find the largest i where t_vals[i] <= t
    i = int(np.searchsorted(spline.t_vals, t, side='right')) - 1
    i = max(0, min(i, spline.n_points - 2))

    h_i = spline.t_vals[i+1] - spline.t_vals[i]

    # a goes from 1 at t_vals[i] down to 0 at t_Vals[i+1]
    # b goes from 0 at t_vals[i] up to 1 at t_vals[i+1]
    a = (spline.t_vals[i+1] - t)/h_i
    b = (t - spline.t_vals[i])/h_i

    def eval_coord(vals, m):
        return a*vals[i] + b*vals[i + 1] + ((a**3 - a)*m[i] + (b**3 - b)*m[i + 1])*h_i**2 / 6.0
    
    x = eval_coord(spline.x_vals, spline.mx)
    y = eval_coord(spline.y_vals, spline.my)

    # Round to valid coordinate range 
    x = round(max(0.0, min(1.0, x)), 6)
    y = round(max(0.0, min(1.0, y)), 6)

    return x,y


def fit_splines(window: list[dict]) -> FitResult:
    # window[0] is the newest (by Redis queue order)
    # iterate oldest to newest for ascending time
    per_driver: dict[int, list] = {}
    codes: dict[int, str] = {}

    for snap in reversed(window):
        unix_t = _parse_unix_ts(snap["timestamp"])

        for pos in snap.get("positions", []):
            num = pos["driver_number"]
            pts = per_driver.setdefault(num, [])

            # skip dups & out-of-order times
            if pts and unix_t <= pts[-1][0]:
                continue

            pts.append((unix_t, pos["x_norm"], pos["y_norm"]))
            codes[num] = pos["driver_code"]

    splines = {}
    for num, pts in per_driver.items():
        t_arr = np.array([p[0] for p in pts])
        x_arr = np.array([p[1] for p in pts])
        y_arr = np.array([p[2] for p in pts])

        mx = _fit_natural_cubic_spline(t_arr, x_arr)
        my = _fit_natural_cubic_spline(t_arr, y_arr)

        splines[num] = DriverSpline(
            driver_number = num,
            driver_code = codes[num],
            t_vals = t_arr,
            x_vals = x_arr,
            y_vals = y_arr,
            mx = mx,
            my = my,
            n_points = len(t_arr),
        )

    start = _parse_unix_ts(window[-1]["timestamp"])
    end = _parse_unix_ts(window[LAG]["timestamp"])

    return FitResult(splines=splines, safe_start = start, safe_end=end, window=window)


def interpolate_snapshot(fit: FitResult, t: float, trail_state: dict) -> dict:
    # get most recent snapshot
    ref_snap = fit.window[-1]
    for snap in fit.window:
        if _parse_unix_ts(snap["timestamp"]) <= t:
            ref_snap = snap
            break

    positions = []
    for num, spline in fit.splines.items():
        x, y = evaluate_spline(spline, t)

        trail = trail_state.setdefault(num, [])
        trail.append([x, y])
        if len(trail) > TRAIL_DEPTH:
            trail.pop(0)

        positions.append({
            "driver_number": num,
            "driver_code": spline.driver_code,
            "x_norm": x,
            "y_norm": y,
            "trail": list(trail), # copy so no alias
        })

    return {
        "timestamp": _unix_to_iso(t),
        "positions": positions,
        "leaderboard": ref_snap.get("leaderboard", []),
        "session": ref_snap.get("session", None),
    }