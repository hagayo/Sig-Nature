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


def test_handwriting_artwork_never_reveals_untraced_pixels(tmp_path: Path) -> None:
    from PIL import ImageDraw
    artwork = Image.new("L", (720, 720), 0)
    d = ImageDraw.Draw(artwork)
    d.line(((60, 300), (620, 300)), fill=255, width=6)
    d.line(((60, 420), (620, 420)), fill=255, width=6)  # Not on the pen route.
    path = PenPath(
        ((60, 300), (620, 300)),
        artwork=artwork,
        reveal_width=10,
    )
    final = render_signature(path, tmp_path / "ink.png")
    render_frames(path, tmp_path / "frames")
    with Image.open(final) as ink:
        assert ink.getpixel((300, 300))[3] > 0
        assert ink.getpixel((300, 420))[3] == 0
    with Image.open(tmp_path / "frames" / "frame_000.png") as start:
        assert start.getpixel((540, 300)) == (255, 255, 255)
    with Image.open(tmp_path / "frames" / "frame_035.png") as end:
        assert end.getpixel((300, 300))[:3] == (25, 42, 115)
        assert end.getpixel((300, 420)) == (255, 255, 255)


def test_all_frames_reveal_only_prefixes_of_one_stroke(tmp_path: Path) -> None:
    from PIL import ImageDraw
    art = Image.new("L", (720, 720), 0)
    ImageDraw.Draw(art).line([(90, 360), (610, 360)], fill=255, width=6)
    path = PenPath(((90, 360), (610, 360)), artwork=art, reveal_width=12)
    folder = tmp_path / "frames"
    render_frames(path, folder)
    # Inspect transparent ink, not the pen barrel that may cover the live tip.
    from backend.pen_path import _ink_layer
    seen = set()
    for step in range(FRAME_COUNT):
        progress = ((step + 1) / FRAME_COUNT) ** (1.3 - .6 * path.tempo)
        ink = _ink_layer(
            path.trace(progress), (720, 720), path.artwork, path.reveal_width,
        )
        visible = {
            x for x in range(100, 550, 10)
            if ink.getpixel((x, 360))[3] > 0
        }
        assert seen.issubset(visible)
        seen = visible
    assert len(seen) >= 40
