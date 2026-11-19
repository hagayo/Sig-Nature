"""Prototype single-stroke Hebrew signature planner.

Each glyph is a directed polyline. Connections between letters and words
are visible ink, never pen-up jumps. This is a geometric prototype, not
a handwriting-quality guarantee.
"""

from hashlib import sha256
from math import cos, pi, sin
import unicodedata

from backend.pen_path import PenPath, Point

# Glyphs use normalized (x, y), with x=1 at the right and x=0 at the left.
# All letter paths start near their right side and proceed along pen travel.
GLYPHS: dict[str, tuple[Point, ...]] = {
    "א": ((1,.2),(.55,.65),(.12,.1),(.48,.55),(.75,.12),(.1,.8)),
    "ב": ((.95,.18),(.35,.16),(.18,.32),(.23,.7),(.85,.72),(.1,.75)),
    "ג": ((.95,.15),(.5,.2),(.45,.5),(.12,.85),(.45,.5),(.7,.78)),
    "ד": ((.95,.22),(.1,.2),(.3,.22),(.3,.85)),
    "ה": ((.95,.22),(.2,.2),(.2,.65),(.32,.65),(.5,.22),(.72,.65)),
    "ו": ((.8,.2),(.7,.35),(.65,.8)),
    "ז": ((.95,.2),(.4,.2),(.5,.3),(.5,.8)),
    "ח": ((.95,.8),(.9,.2),(.2,.2),(.15,.8)),
    "ט": ((.95,.2),(.85,.7),(.45,.82),(.15,.65),(.2,.2),(.4,.15)),
    "י": ((.8,.2),(.65,.42),(.55,.3)),
    "כ": ((.95,.2),(.35,.18),(.15,.38),(.3,.72),(.9,.73)),
    "ך": ((.95,.2),(.3,.18),(.2,.4),(.4,1.2)),
    "ל": ((.95,.35),(.65,.15),(.5,-.4),(.35,.2),(.2,.8)),
    "מ": ((.95,.75),(.8,.2),(.4,.2),(.2,.75),(.75,.72),(.3,.35),(.1,.7)),
    "ם": ((.95,.2),(.2,.2),(.2,.75),(.9,.75),(.95,.2)),
    "נ": ((.85,.2),(.7,.65),(.45,.75),(.15,.72)),
    "ן": ((.8,.2),(.6,.55),(.5,1.2)),
    "ס": ((.95,.2),(.25,.18),(.15,.5),(.35,.8),(.8,.75),(.95,.2)),
    "ע": ((.95,.2),(.7,.75),(.4,.72),(.2,.2),(.4,.72),(.12,.78)),
    "פ": ((.95,.2),(.3,.2),(.15,.5),(.35,.75),(.85,.75),(.7,.45)),
    "ף": ((.95,.2),(.3,.2),(.15,.5),(.35,.75),(.8,.75),(.5,1.2)),
    "צ": ((.95,.2),(.7,.65),(.2,.8),(.55,.55),(.3,.2)),
    "ץ": ((.95,.2),(.7,.65),(.3,1.2),(.65,.6),(.3,.2)),
    "ק": ((.95,.2),(.2,.2),(.2,.65),(.5,.7),(.6,.35),(.65,1.15)),
    "ר": ((.95,.2),(.35,.2),(.3,.45),(.35,.8)),
    "ש": ((.95,.2),(.85,.7),(.55,.75),(.5,.2),(.45,.75),(.2,.7),(.15,.2)),
    "ת": ((.95,.2),(.15,.2),(.25,.75),(.55,.75),(.8,.25),(.9,.75)),
}


def plan_signature(\n    full_name: str,\n    size: tuple[int, int] = (720, 720),\n    portrait: bytes = b"",\n) -> PenPath:
    """Plan a reproducible RTL, uninterrupted trajectory for a Hebrew name.

    Whitespace is represented by a continuous low connector stroke.
    Non-Hebrew letters are rejected instead of silently producing wrong text.
    """
    normalized = unicodedata.normalize("NFC", full_name).strip()
    words = normalized.split()
    if not words:
        raise ValueError("Full name must not be empty")
    letters = [character for word in words for character in word]
    unsupported = sorted(set(letters) - GLYPHS.keys())
    if unsupported:
        raise ValueError(f"Unsupported characters: {''.join(unsupported)}")
    if len(letters) > 32:
        raise ValueError("Name exceeds 32 letters")
    if min(size) < 100:
        raise ValueError("Canvas is too small")

    # Portrait bytes influence the geometry, not merely the filename.
    # This does NOT detect facial expression or infer emotion.
    digest = sha256(normalized.encode("utf-8") + b"\\x00" + portrait).digest()
    portrait_style = sha256(portrait).digest() if portrait else bytes(32)
    width_factor = 0.90 + portrait_style[0] / 255 * 0.20
    height_factor = 0.90 + portrait_style[1] / 255 * 0.20
    letter_width = min(55.0, (size[0] - 110) / (len(letters) + .65 * (len(words)-1)))
    letter_width *= width_factor\n    baseline = size[1] * .53
    height = min(95.0, size[1] * .16) * height_factor
    x_right = size[0] - 55.0
    result: list[Point] = []

    for word_index, word in enumerate(words):
        if word_index:
            x_right -= letter_width * .65
        for char_index, char in enumerate(word):
            ordinal = len(result)
            style = digest[(word_index * 7 + char_index) % len(digest)]
            slant = (style % 13 - 6) / 120
            glyph = GLYPHS[char]
            points = [
                (
                    x_right - (1 - gx) * letter_width + slant * gy * height,
                    baseline + (gy - .5) * height,
                )
                for gx, gy in glyph
            ]
            if result:
                start = result[-1]
                end = points[0]
                # A visible, curved ink connector: the pen stays down.
                middle = ((start[0] + end[0]) / 2, max(start[1], end[1]) + 9)
                result.extend((middle, end))
            result.extend(points if not ordinal else points[1:])
            x_right -= letter_width
    # A name-specific flourish continues from the last stroke, without lifting.
    tail = result[-1]
    phase = (digest[-1] / 255) * pi
    result.extend((
        (tail[0] - 10, tail[1] + 12),
        (tail[0] - 35, tail[1] + 17 + 6 * sin(phase)),
        (tail[0] - 58, tail[1] + 10 + 5 * cos(phase)),
    ))
    # Fit the complete stroke, including ascenders, descenders and flourish.
    min_x = min(point[0] for point in result)
    max_x = max(point[0] for point in result)
    min_y = min(point[1] for point in result)
    max_y = max(point[1] for point in result)
    scale = min((size[0]-90)/(max_x-min_x), (size[1]-160)/(max_y-min_y))
    offset_x = (size[0] - (max_x-min_x)*scale) / 2
    offset_y = (size[1] - (max_y-min_y)*scale) / 2
    fitted = tuple(
        (offset_x + (x-min_x)*scale, offset_y + (y-min_y)*scale)
        for x, y in result
    )
    return PenPath(fitted)
