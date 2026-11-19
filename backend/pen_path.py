"""Deterministic, single-contact pen trajectory and frame renderer.

A path is an ordered polyline, not a bitmap. All frames share the same path
and reveal its prefix by arc length, so no disconnected ink can appear.
"""

from dataclasses import dataclass
from math import hypot, isfinite
from pathlib import Path

from PIL import Image, ImageDraw

from backend.animation import FRAME_COUNT

Point = tuple[float, float]
INK = (25, 42, 115, 255)


@dataclass(frozen=True)
class PenPath:
    """One continuous sequence of pen positions in image pixel coordinates."""

    points: tuple[Point, ...]

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("Pen path needs at least two points")
        for index, (x, y) in enumerate(self.points):
            if not isfinite(x) or not isfinite(y):
                raise ValueError(f"Non-finite pen position at point {index}")
        if self.length <= 0:
            raise ValueError("Pen path has zero length")

    @property
    def length(self) -> float:
        """Total traveled distance, including retraced strokes."""
        return sum(
            hypot(b[0] - a[0], b[1] - a[1])
            for a, b in zip(self.points, self.points[1:])
        )

    def prefix(self, fraction: float) -> tuple[Point, ...]:
        """Return the exact arc-length prefix, including interpolated tip."""
        if not 0 <= fraction <= 1 or not isfinite(fraction):
            raise ValueError("Progress must be finite and between 0 and 1")
        remaining = self.length * fraction
        result = [self.points[0]]
        for start, end in zip(self.points, self.points[1:]):
            distance = hypot(end[0] - start[0], end[1] - start[1])
            if distance == 0:
                continue
            if remaining >= distance:
                result.append(end)
                remaining -= distance
            else:
                result.append((
                    start[0] + (end[0] - start[0]) * remaining / distance,
                    start[1] + (end[1] - start[1]) * remaining / distance,
                ))
                break
        return tuple(result)


def _ink_layer(path: tuple[Point, ...], size: tuple[int, int]) -> Image.Image:
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    if len(path) > 1:
        draw.line(path, fill=INK, width=3, joint="curve")
    x, y = path[-1]
    draw.ellipse((x - 1.5, y - 1.5, x + 1.5, y + 1.5), fill=INK)
    return image


def render_frames(
    path: PenPath,
    frames_dir: Path,
    size: tuple[int, int] = (720, 720),
) -> None:
    """Render exactly 36 frames, with ink only at the current pen prefix."""
    if any(dimension <= 0 for dimension in size):
        raise ValueError("Canvas dimensions must be positive")
    if any(not (0 <= x < size[0] and 0 <= y < size[1]) for x, y in path.points):
        raise ValueError("Pen path contains a point outside the canvas")
    frames_dir.mkdir(parents=True, exist_ok=True)
    for index in range(FRAME_COUNT):
        progress = (index + 1) / FRAME_COUNT
        prefix = path.prefix(progress)
        paper = Image.new("RGBA", size, "white")
        paper.alpha_composite(_ink_layer(prefix, size))
        tip_x, tip_y = prefix[-1]
        pen = ImageDraw.Draw(paper)
        # Ballpoint barrel ends exactly at the current ink endpoint.
        pen.line(
            ((tip_x + 35, tip_y - 85), (tip_x, tip_y)),
            fill=(65, 80, 125, 255),
            width=11,
        )
        pen.line(
            ((tip_x + 8, tip_y - 19), (tip_x, tip_y)),
            fill=(170, 175, 185, 255),
            width=5,
        )
        paper.convert("RGB").save(frames_dir / f"frame_{index:03d}.png")


def render_signature(
    path: PenPath, output: Path, size: tuple[int, int] = (720, 720)
) -> Path:
    """Export only the final ink, with transparent background."""
    if any(not (0 <= x < size[0] and 0 <= y < size[1]) for x, y in path.points):
        raise ValueError("Pen path contains a point outside the canvas")
    output.parent.mkdir(parents=True, exist_ok=True)
    _ink_layer(path.points, size).save(output)
    return output
