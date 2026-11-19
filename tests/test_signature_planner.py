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


@pytest.mark.parametrize("name", ["", "   ", "abc", "חגי 123"])
def test_invalid_name_is_rejected(name: str) -> None:
    with pytest.raises(ValueError):
        plan_signature(name)


def test_progression_has_no_pen_lift() -> None:
    path = plan_signature("חגי און")
    for step in range(1, 37):
        prefix = path.prefix(step / 36)
        assert prefix[0] == path.points[0]
        assert prefix[-1] in path.points or len(prefix) > 1
