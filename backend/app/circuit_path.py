"""Arc-length parameterisation of a circuit SVG polyline.

Parses the <polyline points="..."> from a circuit SVG file and provides a
`t_to_xy(t)` function that maps fractional lap progress t ∈ [0, 1) to
normalised (x_norm, y_norm) coordinates suitable for the frontend.

Coordinate convention
---------------------
SVG viewBox is 0 0 1000 1000.  The frontend places dots as:
    left = x_norm * 100%
    top  = (1 − y_norm) * 100%
So we flip Y when converting from SVG space:
    x_norm = x_svg / 1000
    y_norm = 1.0 − y_svg / 1000
"""
from __future__ import annotations

import bisect
import math
import re

VIEWBOX = 1000.0


def _parse_svg_points(svg_path: str) -> list[tuple[float, float]]:
    """Return list of (x_norm, y_norm) from the first polyline in the SVG."""
    text = open(svg_path).read()
    m = re.search(r'points="([^"]+)"', text)
    if not m:
        raise ValueError(f"No polyline points found in {svg_path}")
    pts: list[tuple[float, float]] = []
    for pair in m.group(1).split():
        x_str, y_str = pair.split(",")
        pts.append((
            float(x_str) / VIEWBOX,
            1.0 - float(y_str) / VIEWBOX,  # flip Y axis
        ))
    return pts


def _build_arc_lengths(pts: list[tuple[float, float]]) -> list[float]:
    """Return cumulative arc-length at each point (starts at 0)."""
    lengths: list[float] = [0.0]
    for i in range(1, len(pts)):
        dx = pts[i][0] - pts[i - 1][0]
        dy = pts[i][1] - pts[i - 1][1]
        lengths.append(lengths[-1] + math.sqrt(dx * dx + dy * dy))
    return lengths


class CircuitPath:
    """Holds the arc-length parameterised path for a single circuit."""

    def __init__(self, svg_path: str) -> None:
        self._pts = _parse_svg_points(svg_path)
        self._lengths = _build_arc_lengths(self._pts)
        self._total = self._lengths[-1]

    def t_to_xy(self, t: float) -> tuple[float, float]:
        """Map fractional lap progress t ∈ [0, 1) to (x_norm, y_norm)."""
        target = (t % 1.0) * self._total
        # Binary search for the enclosing segment
        hi = bisect.bisect_left(self._lengths, target)
        hi = min(hi, len(self._pts) - 1)
        lo = max(hi - 1, 0)
        seg = self._lengths[hi] - self._lengths[lo]
        frac = (target - self._lengths[lo]) / seg if seg > 1e-9 else 0.0
        x = self._pts[lo][0] + frac * (self._pts[hi][0] - self._pts[lo][0])
        y = self._pts[lo][1] + frac * (self._pts[hi][1] - self._pts[lo][1])
        return x, y
