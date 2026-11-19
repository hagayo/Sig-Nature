"""Verify portrait impressions and their writing rules without API charges."""
from dataclasses import asdict
from io import BytesIO
import json
import math

import pytest
from PIL import Image

from backend.portrait_analysis import PortraitStyle, parse_style, validate_portrait
from backend.style_mapping import style_from_portrait


def test_parse_full_visual_analysis() -> None:
    values = asdict(PortraitStyle(joy=1.0, anger=0.0))
    assert parse_style(json.dumps(values)) == PortraitStyle(joy=1.0, anger=0.0)


@pytest.mark.parametrize("override", [
    {"joy": 1.3}, {"joy": -0.1}, {"joy": True}, {"joy": None},
    {"joy": float("nan")}, {"joy": "happy"},
])
def test_reject_invalid_model_output(override: dict[str, object]) -> None:
    data = asdict(PortraitStyle())
    data.update(override)
    with pytest.raises(ValueError):
        parse_style(json.dumps(data))


def test_missing_field_fails() -> None:
    values = asdict(PortraitStyle())
    values.pop("joy")
    with pytest.raises(ValueError):
        parse_style(json.dumps(values))


def test_visual_moods_affect_style_parameters() -> None:
    stressed = style_from_portrait(PortraitStyle(tension=1, anger=1, tough=1,
                                               softness=0, calm=0))
    calm = style_from_portrait(PortraitStyle(tension=0, anger=0, tough=0,
                                           softness=1, calm=1))
    assert stressed.pressure > calm.pressure
    assert stressed.roundness < calm.roundness
    joyful = style_from_portrait(PortraitStyle(joy=1, sadness=0))
    sad = style_from_portrait(PortraitStyle(joy=0, sadness=1))
    assert joyful.rise > sad.rise


def test_real_png_is_accepted() -> None:
    output = BytesIO()
    Image.new("RGB", (80, 80), "white").save(output, format="PNG")
    assert validate_portrait(output.getvalue()) == "image/png"


def test_fake_png_is_rejected() -> None:
    with pytest.raises(ValueError):
        validate_portrait(b"\\x89PNG\\r\\n\\x1a\\n" + b"broken")


def test_over_limit_rejected() -> None:
    with pytest.raises(ValueError):
        validate_portrait(b"0" * (8 * 1024 * 1024 + 1))
