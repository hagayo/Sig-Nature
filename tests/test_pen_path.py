"""Behavioral tests for continuous-contact pen path rendering."""

from pathlib import Path

import pytest
from PIL import Image

from backend.animation import FRAME_COUNT
from backend.pen_path import PenPath, render_frames, render_signature


def test_arc_length_progress_includes_retracing() -> None:
    path = PenPath(((10, 10), (110, 10), (10, 10)))
    assert path.length == 200
    assert path.prefix(0.25)[-1] == (60, 10)
    assert path.prefix(0.75)[-1] == (60, 10)
    assert path.prefix(1)[-1] == (10, 10)


def test_progress_is_monotonic_along_ordered_path() -> None:
    path = PenPath(((5, 5), (105, 5), (105, 105)))
    assert path.prefix(0.25)[-1] == (55, 5)
    assert path.prefix(0.75)[-1] == (105, 55)


@pytest.mark.parametrize(
    "points",
    [(), ((0, 0),), ((0, 0), (0, 0)), ((0, 0), (float("nan"), 1))],
)
def test_invalid_paths_rejected(points: tuple[tuple[float, float], ...]) -> None:
    with pytest.raises(ValueError):
        PenPath(points)


def test_render_progress_and_transparent_final(tmp_path: Path) -> None:
    path = PenPath(((50, 100), (650, 100)))
    frames_dir = tmp_path / "frames"
    render_frames(path, frames_dir)
    frames = sorted(frames_dir.glob("frame_*.png"))
    assert len(frames) == FRAME_COUNT
    with Image.open(frames[0]) as first, Image.open(frames[-1]) as last:
        assert first.getpixel((500, 100)) == (255, 255, 255)
        assert last.getpixel((500, 100))[:3] == (25, 42, 115)
    output = render_signature(path, tmp_path / "signature.png")
    with Image.open(output) as signature:
        assert signature.mode == "RGBA"
        assert signature.getpixel((500, 500))[3] == 0
        assert signature.getpixel((500, 100))[3] == 255


def test_out_of_bounds_path_rejected(tmp_path: Path) -> None:
    path = PenPath(((1, 1), (800, 1)))
    with pytest.raises(ValueError, match="outside"):
        render_frames(path, tmp_path)
