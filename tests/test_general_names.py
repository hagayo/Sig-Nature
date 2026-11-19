"""General-name contract: layout, scripts, styles, diacritics and safety.

These tests run fully offline: both open-source handwriting fonts are bundled.
They deliberately exercise different users, not just the original sample.
"""
import pytest
from PIL import Image

from backend.name_rules import prepare_name
from backend.pen_path import render_signature
from backend.portrait_analysis import PortraitStyle
from backend.signature_planner import plan_signature, validate_name
from backend.style_mapping import style_from_portrait


@pytest.mark.parametrize(("source","normalized","scripts"), [
    ("חגי און", "חגי און", ("he","he")),
    ("אֲבִיגַיִל לֵוִי", "אביגיל לוי", ("he","he")),
    ("בן־דוד", "בן דוד", ("he","he")),
    ("ג׳ורג׳ כהן", "גורג כהן", ("he","he")),
    ("O'Connor", "OConnor", ("en",)),
    ("Jean-Paul Dupont", "Jean Paul Dupont", ("en","en","en")),
    ("José García", "Jose Garcia", ("en","en")),
    ("François Müller", "Francois Muller", ("en","en")),
    ("Søren Ægir", "Soren AEgir", ("en","en")),
    ("שרה Smith", "שרה Smith", ("he","en")),
    ("Hagay און", "Hagay און", ("en","he")),
    ("דניSmith", "דניSmith", ("he","en")),
])
def test_names_normalize_predictably(
    source: str, normalized: str, scripts: tuple[str,...],
) -> None:
    result = prepare_name(source)
    assert result.display == normalized
    assert tuple(run.script for run in result.runs) == scripts
    assert result.letter_count == sum(len(run.text) for run in result.runs)
    assert validate_name(source)[0] == normalized


@pytest.mark.parametrize("name", [
    "חגי און", "שרה לוי", "משה כהן", "אברהם בן דוד",
    "אביגיל רוזנשטיין", "דוד", "א", "ג׳ורג׳",
    "Hagay Onn", "Sarah Levi", "John Smith", "O'Connor",
    "Jean-Paul Dupont", "José García", "Anna Maria",
    "שרה Smith", "Hagay און", "דניSmith",
])
def test_every_supported_name_produces_fitted_visible_ink(name: str) -> None:
    path = plan_signature(name, portrait=b"fixed-testing-portrait")
    assert path.length > 0
    assert path.artwork is not None
    assert path.artwork.mode == "L"
    assert path.artwork.getbbox() is not None
    assert len(path.points) == len(path.pressures)
    assert 0.0 < path.tempo <= 1.
    assert all(0 <= x < 720 and 0 <= y < 720 for x,y in path.points)
    assert max(
        ((b[0]-a[0])**2 + (b[1]-a[1])**2)**.5
        for a,b in zip(path.points,path.points[1:])
    ) < 10
    assert path.prefix(1.)[-1] == path.points[-1]


def test_distinct_people_and_visual_styles_have_distinct_signatures() -> None:
    happy = style_from_portrait(
        PortraitStyle(joy=1, playful=1, cute=1, tension=0, sadness=0)
    )
    serious = style_from_portrait(
        PortraitStyle(tough=1, tension=1, anger=.8, joy=0, softness=0)
    )
    a = plan_signature("דני לוי", portrait=b"photo-a", style=happy)
    b = plan_signature("דני לוי", portrait=b"photo-a", style=serious)
    c = plan_signature("דני לוי", portrait=b"photo-b", style=happy)
    d = plan_signature("נועה לוי", portrait=b"photo-a", style=happy)
    assert a.points != b.points
    assert a.artwork.tobytes() != b.artwork.tobytes()
    assert a.points != c.points
    assert a.points != d.points


@pytest.mark.parametrize("bad_name", [
    "", "   ", "חגי123", "Hagay_123", "אבג😀",
    "\u202eabc", "ab\x00cd", "אבג/כהן", "東京 太郎",
    "اسم عربي", "Αλέξανδρος", "A"*49,
    "A B C D E F G",
])
def test_invalid_or_unsupported_names_are_rejected_without_paid_api(
    bad_name: str,
) -> None:
    with pytest.raises(ValueError):
        prepare_name(bad_name)


def test_long_name_and_final_flourish_remain_inside_png(tmp_path) -> None:
    name = "אבגדהוזחטיכלמנסעפצקרשתךםןףץ"
    path = plan_signature(name)
    png = render_signature(path, tmp_path/"long_name.png")
    with Image.open(png) as image:
        bbox=image.getchannel("A").getbbox()
        assert bbox is not None
        assert 0 < bbox[0] < bbox[2] < 720
        assert 0 < bbox[1] < bbox[3] < 720


def test_script_fonts_are_packaged_with_license() -> None:
    from pathlib import Path
    assets=Path(__file__).resolve().parent.parent/"backend"/"assets"
    for name in ("GveretLevin", "Caveat"):
        assert any(p.name.startswith(name) and p.suffix==".ttf"
                   for p in assets.iterdir())
        assert (assets / (name+"-OFL.txt")).is_file()


@pytest.mark.parametrize("canvas", [
    (160,160), (256,256), (720,720), (1280,640),
])
@pytest.mark.parametrize("name", ["א", "שרה לוי", "Hagay Onn", "שרה Smith"])
def test_general_composer_fits_rectangular_and_small_canvases(
    canvas: tuple[int,int], name: str,
) -> None:
    path = plan_signature(name, size=canvas)
    assert path.artwork is not None and path.artwork.size == canvas
    assert path.artwork.getbbox() is not None
    assert all(0 <= x < canvas[0] and 0 <= y < canvas[1]
               for x,y in path.points)


def test_same_name_with_diacritics_produces_same_geometric_identity() -> None:
    direct = plan_signature("Jose Garcia", portrait=b"same-face")
    accents = plan_signature("José García", portrait=b"same-face")
    assert direct.points == accents.points
    assert direct.artwork.tobytes() == accents.artwork.tobytes()
