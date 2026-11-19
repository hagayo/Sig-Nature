"""A single continuous, style-responsive signature stroke for a full name.

Every glyph and visible inter-glyph connector belongs to one pen-down polyline.
The photo's artistic analysis influences glyph geometry before rasterization.
"""
from hashlib import sha256
from math import cos, pi, sin
import unicodedata

from backend.pen_path import PenPath, Point
from backend.style_mapping import WritingStyle

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


# Simplified single-path cursive Latin glyphs. Hebrew remains the primary alphabet.
LATIN: dict[str, tuple[Point, ...]] = {
    "a": ((1,.65),(.8,.3),(.35,.25),(.12,.52),(.3,.78),(.8,.7),(.65,.3),(.12,.76)),
    "b": ((.9,-.28),(.76,.77),(.6,.4),(.25,.28),(.1,.58),(.35,.78),(.8,.63),(.15,.75)),
    "c": ((.9,.28),(.45,.22),(.12,.5),(.45,.78),(.87,.7)),
    "d": ((.85,.32),(.5,.22),(.15,.5),(.4,.78),(.83,.72),(.9,-.25),(.63,.66),(.1,.75)),
    "e": ((.87,.52),(.23,.48),(.35,.25),(.75,.26),(.68,.7),(.12,.75)),
    "f": ((.9,-.25),(.62,.28),(.55,.82),(.25,1.03),(.4,.5),(.85,.48),(.1,.74)),
    "g": ((.87,.32),(.4,.25),(.1,.5),(.42,.78),(.81,.67),(.7,.28),(.55,1.12),(.18,1.02),(.13,.72)),
    "h": ((.9,-.25),(.75,.78),(.61,.39),(.3,.25),(.21,.57),(.15,.8)),
    "i": ((.84,.31),(.62,.36),(.55,.72),(.1,.75)),
    "j": ((.78,.32),(.56,.98),(.25,1.08),(.1,.82)),
    "k": ((.91,-.25),(.7,.82),(.67,.56),(.2,.28),(.62,.57),(.1,.8)),
    "l": ((.88,-.25),(.63,.72),(.25,.82),(.1,.72)),
    "m": ((.96,.38),(.79,.74),(.7,.39),(.49,.28),(.43,.7),(.35,.4),(.14,.29),(.1,.77)),
    "n": ((.9,.35),(.74,.75),(.58,.39),(.3,.27),(.2,.75),(.1,.74)),
    "o": ((.85,.35),(.42,.23),(.12,.5),(.43,.76),(.85,.62),(.78,.35),(.1,.72)),
    "p": ((.9,.35),(.7,1.12),(.65,.55),(.3,.28),(.1,.5),(.38,.75),(.65,.57),(.1,.73)),
    "q": ((.87,.34),(.44,.23),(.13,.54),(.45,.76),(.81,.64),(.7,1.1),(.4,1.04),(.1,.72)),
    "r": ((.9,.35),(.68,.7),(.53,.39),(.27,.29),(.1,.45)),
    "s": ((.85,.32),(.38,.26),(.35,.48),(.75,.62),(.53,.78),(.1,.72)),
    "t": ((.79,-.12),(.62,.7),(.3,.78),(.1,.69),(.3,.38),(.92,.38)),
    "u": ((.88,.32),(.72,.72),(.44,.78),(.32,.35),(.25,.7),(.1,.76)),
    "v": ((.9,.29),(.66,.77),(.45,.72),(.12,.3)),
    "w": ((.95,.3),(.74,.75),(.58,.52),(.47,.74),(.27,.72),(.1,.3)),
    "x": ((.85,.3),(.18,.75),(.47,.52),(.76,.72),(.1,.3)),
    "y": ((.88,.3),(.69,.72),(.42,.78),(.3,.32),(.43,.87),(.16,1.1),(.1,.8)),
    "z": ((.9,.3),(.25,.29),(.69,.76),(.15,.75)),
}


def _curve(anchors: list[Point], rounding: float, resolution: int = 7) -> list[Point]:
    """Smooth an ordered path without moving its anchors or breaking continuity."""
    if not anchors:
        return []
    out = [anchors[0]]
    for i in range(len(anchors) - 1):
        p0 = anchors[max(0, i-1)]
        p1, p2 = anchors[i], anchors[i+1]
        p3 = anchors[min(len(anchors)-1, i+2)]
        # Hermite tangents, with strength controlled by artistic roundness.
        tension = .45 * rounding
        m1 = ((p2[0]-p0[0])*tension, (p2[1]-p0[1])*tension)
        m2 = ((p3[0]-p1[0])*tension, (p3[1]-p1[1])*tension)
        for j in range(1, resolution+1):
            t = j/resolution
            h00, h10 = 2*t**3-3*t**2+1, t**3-2*t*t+t
            h01, h11 = -2*t**3+3*t*t, t**3-t*t
            cx = h00*p1[0]+h10*m1[0]+h01*p2[0]+h11*m2[0]
            cy = h00*p1[1]+h10*m1[1]+h01*p2[1]+h11*m2[1]
            linear = (p1[0]+(p2[0]-p1[0])*t, p1[1]+(p2[1]-p1[1])*t)
            blend = .15 + .85*rounding
            out.append((linear[0]*(1-blend)+cx*blend,
                        linear[1]*(1-blend)+cy*blend))
    return out


def _connector(start: Point, end: Point, depth: float) -> list[Point]:
    """A visible quadratic connector, never an invisible pen-up move."""
    middle = ((start[0]+end[0])*.5, max(start[1], end[1])+depth)
    return [
        ((1-t)**2*start[0]+2*(1-t)*t*middle[0]+t*t*end[0],
         (1-t)**2*start[1]+2*(1-t)*t*middle[1]+t*t*end[1])
        for t in (i/10 for i in range(1, 11))
    ]


def plan_signature(
    full_name: str,
    size: tuple[int, int] = (720, 720),
    portrait: bytes = b"",
    style: WritingStyle | None = None,
) -> PenPath:
    """Produce a reproducible RTL (Hebrew) or LTR (Latin) pen-down path.

    Photo-derived style is dominant; photo bytes only seed small glyph-level
    irregularities so even otherwise visually similar photos remain distinctive.
    """
    name = unicodedata.normalize("NFC", full_name).strip()
    words = name.split()
    if not words:
        raise ValueError("Full name is required")
    letters = [c for word in words for c in word]
    if len(letters) > 32:
        raise ValueError("Name exceeds 32 letters")
    if min(size) < 160:
        raise ValueError("Canvas is too small")
    hebrew = all(c in GLYPHS for c in letters)
    latin = all(c.lower() in LATIN for c in letters)
    if not hebrew and not latin:
        raise ValueError("Use Hebrew or English letters only, without mixing scripts")
    alphabet = GLYPHS if hebrew else LATIN
    if style is None:
        style = WritingStyle()
    fingerprint = sha256(name.encode("utf-8") + b"\x00" + portrait).digest()
    letter_width = min(54.0, 580/(len(letters)*style.spacing + len(words)))
    height = 94 * style.height
    advance = letter_width * style.spacing
    x = 650.0
    baseline = 370.0
    path: list[Point] = []
    letter_index = 0
    for wi, word in enumerate(words):
        if wi:
            x -= advance * .67
        for ch in word:
            seed = fingerprint[letter_index % 32]
            shift = (seed/255 - .5)*style.irregularity*height*.25
            width = letter_width*style.width*(1+(seed/255-.5)*style.irregularity*.18)
            anchors = []
            for gx, gy in alphabet[ch.lower() if latin else ch]:
                y = (baseline+(gy-.5)*height
                     -style.rise*letter_index/max(1,len(letters)-1)*height*.60
                     +shift*(.3+gy))
                x_pos = x - (1-gx)*width + style.slant*(gy-.5)*height
                anchors.append((x_pos,y))
            curved = _curve(anchors, style.roundness)
            if path:
                path.extend(_connector(path[-1],curved[0],
                                       height*(.055+.025*style.speed)))
            path.extend(curved if not path else curved[1:])
            x -= advance
            letter_index += 1
    # Finishing movement is still part of the same pen-down path.
    tail = path[-1]
    reach = height*(.2+style.flourish*.95+style.speed*.17)
    lift = height*(style.rise*.40 + style.flourish*.10)
    phase = fingerprint[-1]/255*pi
    flourish_anchors = [
        tail,
        (tail[0]-reach*.32,tail[1]-lift*.35),
        (tail[0]-reach*.65,tail[1]-lift + 3*sin(phase)),
        (tail[0]-reach,tail[1]-lift*.70),
    ]
    if style.flourish > .72:
        flourish_anchors.extend([
            (tail[0]-reach*1.15,tail[1]-lift*.45-height*.17),
            (tail[0]-reach*1.0,tail[1]-lift*.22),
        ])
    path.extend(_curve(flourish_anchors,style.roundness)[1:])
    min_x,max_x = min(p[0] for p in path),max(p[0] for p in path)
    min_y,max_y = min(p[1] for p in path),max(p[1] for p in path)
    span_x,span_y = max_x-min_x,max_y-min_y
    scale = min((size[0]-100)/max(1,span_x),(size[1]-170)/max(1,span_y))
    off_x=(size[0]-scale*span_x)/2
    off_y=(size[1]-scale*span_y)/2
    fitted=tuple((off_x+(p[0]-min_x)*scale,off_y+(p[1]-min_y)*scale)
                 for p in path)
    pressures=tuple(
        max(.1,min(1.,style.pressure+(.065+.09*style.irregularity)
                        *sin(i*.39+phase)))
        for i in range(len(fitted))
    )
    return PenPath(fitted, pressures)
