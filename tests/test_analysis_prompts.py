"""No-charge checks of both visual prompts, image preprocessing and model schemas."""
import asyncio
from dataclasses import asdict
from io import BytesIO
import json

import pytest
from PIL import Image, ImageDraw

from backend import portrait_analysis, signature_analysis
from backend.portrait_analysis import PortraitStyle
from backend.signature_analysis import SignatureReport


def portrait() -> bytes:
    stream = BytesIO()
    Image.new("RGB", (128, 128), "beige").save(stream, "JPEG")
    return stream.getvalue()


def signed_page() -> bytes:
    stream = BytesIO()
    image = Image.new("RGBA", (900, 380), (255, 255, 255, 0))
    draw = ImageDraw.Draw(image)
    draw.line([(90, 220), (210, 160), (340, 250), (560, 190)],
              fill=(5, 15, 100, 255), width=2)
    image.save(stream, "PNG")
    return stream.getvalue()


def test_portrait_prompt_surfaces_visible_cues_and_exact_scores(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    answer = {
        "face_visible": True, "visual_summary": "חיוך רחב ומבט ישיר",
        "visual_cues": ["זוויות הפה מורמות", "הראש מוטה קלות"],
        "character_vibe": "דמות חברותית ושובבה",
        "scores": asdict(PortraitStyle(joy=.96, sadness=.04, playful=.93)),
    }
    async def fake_vision(picture, mime, key, instructions, name, schema, **kwargs):
        calls.append((mime, key, instructions, name, schema))
        return json.dumps(answer)
    monkeypatch.setattr(portrait_analysis, "request_vision", fake_vision)
    result = asyncio.run(
        portrait_analysis.analyze_portrait_detailed(portrait(), "temp-key", "he")
    )
    assert result.style.joy == .96
    assert result.style.sadness == .04
    assert result.vibe == "דמות חברותית ושובבה"
    assert result.cues == ("זוויות הפה מורמות", "הראש מוטה קלות")
    mime, key, prompt, name, schema = calls[0]
    assert mime == "image/jpeg"
    assert key == "temp-key"
    assert name == "portrait_signature_style"
    assert "head_tilt" in schema["properties"]["scores"]["required"]
    assert "same person" in prompt.lower()
    assert "natural, clear Hebrew" in prompt


def test_signature_prompt_and_thin_ink_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = []
    answer = asdict(SignatureReport(
        description="Fine handwritten strokes",
        impression="An energetic fictional character's flourish",
        line_pressure="Thin with darker turns",
        rhythm="Flowing",
        slant="Mildly rising",
        connections="Several connected strokes",
        flourish="Long final loop",
        legibility="Some letters clear",
        spacing="Compact",
        letter_shapes="Rounded and simplified",
        baseline="Gently rising",
        stroke_variation="Subtle tapering",
    ))
    async def fake_vision(picture, mime, key, instructions, name, schema, **kwargs):
        calls.append((picture, mime, key, instructions, name, schema))
        return json.dumps(answer)
    monkeypatch.setattr(signature_analysis, "request_vision", fake_vision)
    report = asyncio.run(
        signature_analysis.analyze_signature(signed_page(), "temp-key", "en")
    )
    assert report.flourish == "Long final loop"
    picture, mime, key, prompt, name, schema = calls[0]
    assert mime == "image/png"
    assert key == "temp-key"
    assert name == "signature_analysis"
    assert "signature_visible" in schema["required"]
    assert "actual pen force" in prompt
    assert "natural English" in prompt
    with Image.open(BytesIO(picture)) as image:
        assert image.format == "PNG"
        assert image.mode == "RGB"
        assert any(blue > red for red, green, blue in image.getdata())


def test_no_real_claims_and_no_generic_prompt() -> None:
    face = portrait_analysis.portrait_prompt("en")
    pen = signature_analysis.signature_prompt("he")
    assert "not to discover someone's actual personality" in face
    assert "2-5" in face
    assert "mischievous" in face
    assert "LAST letter" in pen
    assert "not the identity or mental state" in pen
    assert "idiomatic Hebrew" in pen


@pytest.mark.parametrize("language", ["de", "", "javascript"])
def test_unexpected_languages_rejected(language: str) -> None:
    with pytest.raises(ValueError):
        portrait_analysis.portrait_prompt(language)
    with pytest.raises(ValueError):
        signature_analysis.signature_prompt(language)



def test_signature_photo_crops_large_blank_margins_before_scaling() -> None:
    from backend.signature_analysis import prepare_signature_for_vision
    image = Image.new("RGB", (2400, 1200), "white")
    draw = ImageDraw.Draw(image)
    draw.line([(1650, 520), (1800, 490), (2010, 545)],
              fill=(10, 25, 100), width=2)
    original = BytesIO()
    image.save(original, "PNG")
    prepared = prepare_signature_for_vision(original.getvalue())
    with Image.open(BytesIO(prepared)) as crop:
        assert crop.width < 700
        assert crop.height < 300
        assert any(blue > red for red, green, blue in crop.getdata())


def test_whole_image_ink_does_not_trigger_destructive_crop() -> None:
    from backend.signature_analysis import prepare_signature_for_vision
    image = Image.new("RGB", (120, 80), "white")
    draw = ImageDraw.Draw(image)
    draw.line([(1, 1), (119, 79)], fill="navy", width=2)
    source = BytesIO()
    image.save(source, "PNG")
    with Image.open(BytesIO(prepare_signature_for_vision(source.getvalue()))) as result:
        assert result.size == image.size
