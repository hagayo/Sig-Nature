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
FINISH_SECONDS = 1.65


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
        # Plan local pen speed in travelled distance, not skeleton pixels.
        # Slow down near bends, keep flowing connectors moving, and ease
        # naturally into and out of the full signature without lifting.
        turn_field = []
        for i in range(n):
            left = max(0, bisect_right(length, length[i] - 13.0) - 1)
            right = min(n, bisect_right(length, length[i] + 13.0))
            turn_field.append(sum(turns[left:right]) / max(1, right-left))
        targets = []
        for i, bend in enumerate(turn_field):
            progress = length[i] / self.length
            envelope = min(1.0, max(.27, (progress/.06)**.6),
                           max(.25, ((1.-progress)/.065)**.6))
            connector = 1.12 if self.pressures[i] < .30 else 1.0
            targets.append(max(.24, (.94 / (1. + 3.8*bend))*envelope*connector))
        # Forward/backward smoothing removes one-pixel jerks in pen velocity.
        filtered = targets[:]
        for i in range(1, n):
            alpha = min(.45, (length[i]-length[i-1])/7.)
            filtered[i] = filtered[i-1]*(1-alpha)+targets[i]*alpha
        for i in range(n-2,-1,-1):
            alpha = min(.45, (length[i+1]-length[i])/7.)
            filtered[i] = filtered[i+1]*(1-alpha)+filtered[i]*alpha
        complexity = sum(turn_field[i]*(length[i+1]-length[i])
                         for i in range(n-1))/self.length
        # Human-scale writing: elaborate names take longer than a short mark.
        self.writing_seconds = max(5.1, min(10.6,
            4.55 + .085*sqrt(self.length) + 2.1*complexity
            - .85*(path.tempo-.5)))
        raw = [0.]
        for i in range(1,n):
            segment = length[i]-length[i-1]
            speed = max(.19, (filtered[i-1]+filtered[i])/2.)
            raw.append(raw[-1]+segment/speed)
        factor = self.writing_seconds/raw[-1]
        self.times = [instant*factor for instant in raw]
        self.duration = self.writing_seconds + FINISH_SECONDS
        self.frame_count = ceil(self.duration*FRAME_RATE)

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
