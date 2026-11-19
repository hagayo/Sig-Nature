"""Normalize real-world Hebrew and Latin personal names for handwriting.

This module is deliberately independent of fonts and paid vision calls.
It supports accents, Hebrew vowel points, apostrophes, geresh, maqaf,
hyphenated surnames, and mixed Hebrew/Latin tokens while rejecting controls.
"""
from __future__ import annotations

from dataclasses import dataclass
import unicodedata

HEBREW = frozenset("אבגדהוזחטיכלמנסעפצקרשתךםןףץ")
LATIN = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ")
SPACES = frozenset(" \t\n\r\u00a0\u2002\u2003\u2009")
DASHES = frozenset("-‐‑‒–—־")
APOSTROPHES = frozenset("'’‘ʼʻ׳״\"`")
LATIN_FOLDS = {
    "ß": "ss", "ẞ": "SS", "Æ": "AE", "æ": "ae",
    "Œ": "OE", "œ": "oe", "Ø": "O", "ø": "o",
    "Ł": "L", "ł": "l", "Đ": "D", "đ": "d",
    "Þ": "Th", "þ": "th", "Ð": "D", "ð": "d",
    "ı": "i",
}
MAX_LETTERS = 48
MAX_WORDS = 6


@dataclass(frozen=True)
class NameRun:
    text: str
    script: str  # "he" or "en"
    gap_before: bool = False


@dataclass(frozen=True)
class PreparedName:
    display: str
    runs: tuple[NameRun, ...]
    primary_script: str
    letter_count: int


def _script(char: str) -> str:
    if char in HEBREW:
        return "he"
    if char in LATIN:
        return "en"
    raise ValueError("Supported names use Hebrew or Latin letters")


def prepare_name(full_name: str) -> PreparedName:
    """Return the same deterministic Unicode-normalized name for all engines.

    Diacritics are removed for readable handwritten signatures; marks never
    count as letters or appear as disconnected ink. Apostrophes/geresh do not
    break a pen-down word, while hyphens introduce a small word boundary.
    """
    if not isinstance(full_name, str):
        raise ValueError("A name must be text")
    if len(full_name) > 256:
        raise ValueError("Name exceeds input limit")
    folded = "".join(LATIN_FOLDS.get(c, c) for c in full_name)
    normalized = unicodedata.normalize("NFKD", folded)
    chars: list[str] = []
    for c in normalized:
        code = ord(c)
        if unicodedata.category(c) in {"Mn", "Me"}:
            continue
        if c in SPACES or c in DASHES:
            if chars and chars[-1] != " ":
                chars.append(" ")
        elif c in APOSTROPHES:
            continue
        elif c in HEBREW or c in LATIN:
            chars.append(c)
        elif unicodedata.category(c) in {"Cf", "Cc"} or code in (0x202E, 0x202D):
            raise ValueError("Name contains unsupported control characters")
        else:
            raise ValueError("Use Hebrew or Latin letters in the name")
    cleaned = "".join(chars).strip()
    if not cleaned:
        raise ValueError("Full name is required")
    words = cleaned.split()
    count = sum(len(w) for w in words)
    if count > MAX_LETTERS or len(words) > MAX_WORDS:
        raise ValueError("Name is too long for a legible signature")
    segments: list[NameRun] = []
    for word_index, word in enumerate(words):
        parts: list[tuple[str,str]] = []
        for char in word:
            kind = _script(char)
            if not parts or parts[-1][1] != kind:
                parts.append((char, kind))
            else:
                parts[-1] = (parts[-1][0] + char, kind)
        for i, (text, kind) in enumerate(parts):
            segments.append(NameRun(text, kind, gap_before=word_index > 0 and i == 0))
    return PreparedName(cleaned, tuple(segments), _script(cleaned[0]), count)
