"""One entry point for every supported user's personalized signature.

Hebrew, Latin and mixed-script names now share the same measured handwriting
layout and photographic video pipeline. The original one-person glyph sketch
prototype is retired; no name-specific path coordinates remain.
"""
from __future__ import annotations

from backend.name_rules import HEBREW, LATIN as LATIN_CHARACTERS, prepare_name
from backend.pen_path import PenPath
from backend.signature_composer import create_personal_signature
from backend.style_mapping import WritingStyle

GLYPHS = frozenset(HEBREW)
LATIN = frozenset(LATIN_CHARACTERS)


def validate_name(full_name: str) -> tuple[str, bool]:
    """Fast validation before any paid API request or font rendering."""
    person = prepare_name(full_name)
    return person.display, person.primary_script == "he"


def plan_signature(
    full_name: str,
    size: tuple[int, int] = (720, 720),
    portrait: bytes = b"",
    style: WritingStyle | None = None,
) -> PenPath:
    """Compose a continuous, photo-influenced signature with no clipping."""
    return create_personal_signature(
        full_name, style=style, portrait=portrait, size=size,
    )
