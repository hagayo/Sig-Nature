"""Geometric contract tests for the Hebrew signature planner."""

import pytest

from backend.signature_planner import GLYPHS, plan_signature


def test_all_hebrew_letters_have_stroke_definitions() -> None:
    alphabet = "אבגדהוזחטיכלמנסעפצקרשתךםןףץ"
    assert set(alphabet) == set(GLYPHS)


@pytest.mark.parametrize("name", ["חגי און", "שרה לוי", "משה כהן", "אבגדהוזחטיכלמנסעפצקרשתךםןףץ"])
def test_valid_hebrew_name_is_single_bounded_path(name: str) -> None:
    path = plan_signature(name)
    assert len(path.points) > len(name)
    assert path.length > 0
    assert all(0 <= x < 720 and 0 <= y < 720 for x, y in path.points)
    assert path.prefix(1)[-1] == path.points[-1]


def test_same_name_produces_identical_path() -> None:
    assert plan_signature("חגי און") == plan_signature("חגי און")


def test_different_names_produce_different_paths() -> None:
    assert plan_signature("חגי און") != plan_signature("דני כהן")


@pytest.mark.parametrize("name", ["", "   ", "חגי 123", "אבג hello"])
def test_invalid_name_is_rejected(name: str) -> None:
    with pytest.raises(ValueError):
        plan_signature(name)


def test_progression_has_no_pen_lift() -> None:
    path = plan_signature("חגי און")
    for step in range(1, 37):
        prefix = path.prefix(step / 36)
        assert prefix[0] == path.points[0]
        assert prefix[-1] in path.points or len(prefix) > 1

def test_same_name_different_portraits_change_signature() -> None:
    smiling = plan_signature("חגי און", portrait=b"portrait-smiling")
    serious = plan_signature("חגי און", portrait=b"portrait-serious")
    assert smiling != serious


def test_same_name_same_portrait_is_reproducible() -> None:
    photo = b"same-image-content"
    assert plan_signature("חגי און", portrait=photo) == plan_signature(
        "חגי און", portrait=photo
    )

def test_latin_name_supported_without_lifting() -> None:
    path = plan_signature("Hagay Onn")
    assert len(path.points) > 2
    assert path.length > 0


def test_photo_scores_change_actual_pen_geometry() -> None:
    from backend.portrait_analysis import PortraitStyle
    from backend.style_mapping import style_from_portrait

    happy = style_from_portrait(PortraitStyle(joy=1, playful=1, cute=1))
    tense = style_from_portrait(PortraitStyle(tension=1, tough=1, anger=1))
    joyful_ink = plan_signature("חגי און", portrait=b"image-1", style=happy)
    tense_ink = plan_signature("חגי און", portrait=b"image-1", style=tense)
    assert joyful_ink.points != tense_ink.points
    assert joyful_ink.pressures != tense_ink.pressures


def test_visible_expression_dominates_micro_variation() -> None:
    from backend.portrait_analysis import PortraitStyle
    from backend.style_mapping import style_from_portrait

    delighted = style_from_portrait(PortraitStyle(joy=1, sadness=0, energy=1))
    somber = style_from_portrait(PortraitStyle(joy=0, sadness=1, energy=0))
    assert delighted.rise > somber.rise
    assert plan_signature("חגי און", style=delighted) != plan_signature(
        "חגי און", style=somber
    )
