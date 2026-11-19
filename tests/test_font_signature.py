"""Gveret Levin handwriting, continuous pen contact and matching PNG tests."""
from pathlib import Path

import pytest
from PIL import Image, ImageChops

from backend.pen_path import render_signature
from backend.portrait_analysis import PortraitStyle
from backend.signature_planner import plan_signature
from backend.style_mapping import style_from_portrait


@pytest.mark.parametrize("name", [
    "חגי און", "גחאש", "שלום עולם", "אברהם כהן",
    "אבגדהוזחטיכלמנסעפצקרשתךםןףץ",
])
def test_hebrew_letters_are_grounded_in_font_artwork(name: str) -> None:
    path = plan_signature(name)
    assert path.artwork is not None
    assert path.artwork.mode == "L"
    assert path.artwork.getbbox()
    assert len(path.points) > len(name) * 12
    assert len(path.pressures) == len(path.points)
    # No coordinate jump is hidden as an "unwritten" transition.
    assert max(
        ((b[0]-a[0])**2 + (b[1]-a[1])**2) ** .5
        for a, b in zip(path.points, path.points[1:])
    ) < 10


def test_font_ink_visible_in_rendered_png(tmp_path: Path) -> None:
    path = plan_signature("חגי און")
    png = render_signature(path, tmp_path / "signature.png")
    with Image.open(png) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0,0))[3] == 0
        coverage = image.getchannel("A")
        assert coverage.getbbox()
        assert ImageChops.difference(coverage, path.artwork).getbbox() is None


def test_expression_changes_font_geometry_and_ink_pressure() -> None:
    joyful = style_from_portrait(
        PortraitStyle(joy=1, playful=1, cute=1, tension=0, energy=1, sadness=0)
    )
    tense = style_from_portrait(
        PortraitStyle(joy=0, sadness=1, tough=1, anger=1, tension=1, energy=0)
    )
    happy_path = plan_signature("חגי און", style=joyful, portrait=b"happy-image")
    tense_path = plan_signature("חגי און", style=tense, portrait=b"tense-image")
    assert happy_path.points != tense_path.points
    assert happy_path.artwork.tobytes() != tense_path.artwork.tobytes()
    assert happy_path.pressures != tense_path.pressures


def test_determinism_with_identical_portrait() -> None:
    a = plan_signature("חגי און", portrait=b"same-picture")
    b = plan_signature("חגי און", portrait=b"same-picture")
    assert a.points == b.points
    assert a.artwork.tobytes() == b.artwork.tobytes()


def test_pressure_is_visible_in_transparent_ink_not_only_in_video(
    tmp_path: Path,
) -> None:
    from dataclasses import replace
    from backend.style_mapping import WritingStyle
    baseline = WritingStyle()
    light = plan_signature("חגי און", style=replace(baseline, pressure=.2))
    strong = plan_signature("חגי און", style=replace(baseline, pressure=.95))
    light_png = render_signature(light, tmp_path / "light.png")
    strong_png = render_signature(strong, tmp_path / "strong.png")
    with Image.open(light_png) as pale, Image.open(strong_png) as bold:
        assert sum(bold.getchannel("A").getdata()) > sum(
            pale.getchannel("A").getdata()
        )
    assert max(strong.pressures) > min(strong.pressures)
