"""Handwriting-based Hebrew signature, derived from Gveret Levin glyphs.

The open handwriting font supplies recognisable Hebrew letterforms. The pen
route, joins and final flourishes are generated as ONE visible continuous ink
trajectory, never an unrelated overlaid animation.
"""
from pathlib import Path
import os

from PIL import ImageFont

from backend.name_rules import HEBREW


def get_font(
    size: int,
    font_path: str | None = None,
    script: str = "he",
    weight: float = 450,
) -> ImageFont.FreeTypeFont:
    """Load bundled open handwriting fonts without network dependencies.

    A caller-supplied font override remains available for debugging, and the
    Hebrew default preserves the original get_font(size) API.
    """
    if script not in {"he", "en"}:
        raise ValueError("Unsupported handwriting script")
    if not 8 <= size <= 220:
        raise ValueError("Invalid handwriting font size")
    default = (
        Path(__file__).resolve().parent / "assets" /
        ("GveretLevin-Regular.ttf" if script == "he" else "Caveat-Variable.ttf")
    )
    override = (
        font_path
        or os.environ.get("SIG_NATURE_HEBREW_FONT" if script == "he"
                          else "SIG_NATURE_LATIN_FONT")
    )
    font_file = Path(override) if override else default
    if not font_file.is_file():
        raise RuntimeError(
            f"Handwriting font for {script} is unavailable at {font_file}"
        )
    font = ImageFont.truetype(str(font_file), size)
    if script == "en" and hasattr(font, "get_variation_axes"):
        try:
            axes = font.get_variation_axes()
            values = [
                max(axis["minimum"], min(axis["maximum"], float(weight)))
                if "weight" in str(axis["name"]).lower()
                else axis["default"]
                for axis in axes
            ]
            if values:
                font.set_variation_by_axes(values)
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return font

def thin(foreground: set[tuple[int,int]]) -> set[tuple[int,int]]:
    """Zhang-Suen thinning to extract a one-pixel pen trajectory guide."""
    mask = set(foreground)
    around = ((0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1))
    for _ in range(100):
        removed = 0
        for phase in (0,1):
            discard = []
            for x,y in mask:
                n = [(x+dx,y+dy) in mask for dx,dy in around]
                if not 2 <= sum(n) <= 6: continue
                if sum(not n[i] and n[(i+1)%8] for i in range(8)) != 1: continue
                north,east,south,west = n[0],n[2],n[4],n[6]
                if phase == 0 and ((north and east and south) or (east and south and west)): continue
                if phase == 1 and ((north and east and west) or (north and south and west)): continue
                discard.append((x,y))
            mask.difference_update(discard)
            removed += len(discard)
        if not removed: break
    return mask



def create_hebrew_signature(
    name, style, portrait=b"", size=(720,720), font_path=None,
):
    """Legacy API, delegated to the general-purpose handwriting compositor."""
    from backend.signature_composer import create_personal_signature
    return create_personal_signature(
        name, style=style, portrait=portrait, size=size, font_path=font_path,
    )
