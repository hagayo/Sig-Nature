"""Time-parameterized handwriting motion distinct from pen-path geometry.

The profile follows the existing ordered continuous path. Local curvature,
acceleration and the starting/ending gestures determine speed. No points are
reordered, so both PNG and video share one ink trajectory.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from math import acos, ceil, hypot, isfinite, pi, sqrt

FRAME_RATE = 60
FINISH_SECONDS = .50


@dataclass(frozen=True)
class MotionState:
    progress: float
    position: tuple[float, float]
    direction: tuple[float, float]
    pressure: float
    velocity: float


class MotionTimeline:
    """Local curvature-aware timing with a natural ending and pen-clear hold."""

    def __init__(self, path):
        points = path.points
        pressure = path.pressures or (.55,) * len(points)
        samples = [(points[0], pressure[0])]
        for point, force in zip(points[1:], pressure[1:]):
            if hypot(point[0] - samples[-1][0][0],
                     point[1] - samples[-1][0][1]) > 1e-7:
                samples.append((point, force))
        if len(samples) < 2:
            raise ValueError("Movement path must have nonzero length")
        self.points = [sample[0] for sample in samples]
        self.pressures = [sample[1] for sample in samples]
        length = [0.0]
        for first, second in zip(self.points, self.points[1:]):
            length.append(length[-1] + hypot(second[0] - first[0],
                                             second[1] - first[1]))
        self.distance = length
        self.length = length[-1]
        n = len(self.points)
        turns = [0.] * n
        for i in range(1, n - 1):
            # Local spatial lookahead suppresses skeleton pixel jitter.
            distance = 9.
            left = bisect_right(length, max(0, length[i] - distance)) - 1
            right = min(n - 1, bisect_right(length, length[i] + distance))
            a, b, c = self.points[left], self.points[i], self.points[right]
            u = (b[0] - a[0], b[1] - a[1])
            v = (c[0] - b[0], c[1] - b[1])
            norms = hypot(*u) * hypot(*v)
            if norms > 1e-8:
                cosine = max(-1., min(1., (u[0]*v[0] + u[1]*v[1])/norms))
                turns[i] = acos(cosine) / pi
        targets = []
        for i, bend in enumerate(turns):
            lo, hi = max(0, i-4), min(n, i+5)
            bend = sum(turns[lo:hi]) / (hi-lo)
            progress = length[i] / self.length
            envelope = max(.35, min(1., progress/.055, (1-progress)/.065))
            targets.append((.36 + .64/(1 + 3.2*bend*bend)) * envelope)
        weighted_turn = sum(turns) / max(1, n)
        self.writing_seconds = max(2.7, min(6.0,
            2.05 + .047 * sqrt(self.length) + .75 * weighted_turn
            - .52 * (path.tempo - .5)))
        raw = [0.]
        for i in range(1, n):
            segment = length[i] - length[i-1]
            speed = max(.20, (targets[i-1]+targets[i])/2)
            raw.append(raw[-1] + segment/speed)
        factor = self.writing_seconds / raw[-1]
        self.times = [instant * factor for instant in raw]
        self.duration = self.writing_seconds + FINISH_SECONDS
        self.frame_count = ceil(self.duration * FRAME_RATE)

    def at(self, seconds: float) -> MotionState:
        if not isfinite(seconds):
            raise ValueError("Time must be finite")
        t = max(0., min(self.writing_seconds, seconds))
        i = max(0, min(len(self.times)-2, bisect_right(self.times, t)-1))
        dt = self.times[i+1] - self.times[i]
        alpha = 0. if dt <= 0 else max(0., min(1., (t-self.times[i])/dt))
        first, second = self.points[i], self.points[i+1]
        distance = self.distance[i] + alpha * (self.distance[i+1]-self.distance[i])
        dx, dy = second[0]-first[0], second[1]-first[1]
        norm = hypot(dx, dy)
        return MotionState(
            progress=max(0., min(1., distance/self.length)),
            position=(first[0]+alpha*dx, first[1]+alpha*dy),
            direction=(dx/norm, dy/norm),
            pressure=self.pressures[i]*(1-alpha)+self.pressures[i+1]*alpha,
            velocity=0. if t >= self.writing_seconds else norm/max(dt,1e-8),
        )
