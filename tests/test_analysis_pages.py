"""No-charge endpoint regression tests for the two creative analysis pages."""
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from backend import main
from backend.portrait_analysis import (
    NoVisibleFaceError, PortraitReading, PortraitStyle, parse_reading,
)
from backend.signature_analysis import (
    NoVisibleSignatureError, SignatureReport, parse_report,
)

client = TestClient(main.app)


def picture() -> bytes:
    image = Image.new("RGB", (96, 96), (235, 222, 201))
    out = BytesIO()
    image.save(out, "PNG")
    return out.getvalue()


def test_three_html_pages_use_the_same_design_system() -> None:
    for route, mode in (
        ("/", "generate"),
        ("/analyze-photo.html", "photo"),
        ("/analyze-signature.html", "signature"),
    ):
        response = client.get(route)
        assert response.status_code == 200
        html = response.text
        assert f'data-page="{mode}"' in html
        assert 'href="/style.css"' in html
        assert 'src="/script.js"' in html
        assert 'class="page-shell"' in html
        assert 'class="site-nav"' in html
        assert 'id="language-toggle"' in html
    css = client.get("/style.css").text
    assert ":root" in css
    for token in ("--color-primary", "--radius-sm", "--space-4", "--control-height"):
        assert token in css


def test_photo_analysis_exposes_exact_style_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def vision(portrait: bytes, api_key: str, language: str) -> PortraitReading:
        assert portrait == picture()
        assert api_key == "temporary-key"
        assert language == "he"
        return PortraitReading(
            style=PortraitStyle(joy=1, sadness=0, tension=.2, playful=.9),
            summary="חיוך רחב ומבט פעיל",
            cues=("זוויות הפה מורמות", "עיניים מכווצות קלות"),
            vibe="דמות משחקית ונמרצת",
        )

    monkeypatch.setattr(main, "analyze_portrait_detailed", vision)
    response = client.post(
        "/api/analyze-photo",
        data={"api_key": "temporary-key", "language": "he"},
        files={"image": ("portrait.png", picture(), "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["traits"]["joy"] == 1
    assert data["summary"] == "חיוך רחב ומבט פעיל"
    assert len(data["cues"]) == 2
    assert data["vibe"] == "דמות משחקית ונמרצת"
    assert data["writing_style"]["flourish"] > .5
    assert "password" not in str(data)
    assert "temporary-key" not in str(data)


def test_signature_analysis_uses_the_requested_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def vision(image: bytes, api_key: str, language: str) -> SignatureReport:
        assert image == picture()
        assert api_key == "temporary-key"
        assert language == "en"
        return SignatureReport(
            description="Freehand strokes",
            impression="A playful fictional character",
            line_pressure="Heavy-looking line", rhythm="Brisk",
            slant="Right", connections="Curved", flourish="Extended",
            legibility="Partly legible",
        )

    monkeypatch.setattr(main, "analyze_signature", vision)
    response = client.post(
        "/api/analyze-signature",
        data={"api_key": "temporary-key", "language": "en"},
        files={"image": ("signature.png", picture(), "image/png")},
    )
    assert response.status_code == 200
    data = response.json()["analysis"]
    assert data["description"] == "Freehand strokes"
    assert data["features"]["flourish"] == "Extended"


def test_invalid_image_rejected_before_vision(monkeypatch: pytest.MonkeyPatch) -> None:
    async def forbidden(*args: object) -> None:
        raise AssertionError("Must not contact external model")

    monkeypatch.setattr(main, "analyze_portrait_detailed", forbidden)
    monkeypatch.setattr(main, "analyze_signature", forbidden)
    for route in ("/api/analyze-photo", "/api/analyze-signature"):
        response = client.post(
            route,
            data={"api_key": "test", "language": "he"},
            files={"image": ("bad.png", b"broken", "image/png")},
        )
        assert response.status_code == 415


def test_signature_model_response_validated() -> None:
    import json
    report = {
        "description": "Fine cursive",
        "impression": "Playful style",
        "line_pressure": "Light",
        "rhythm": "Fast",
        "slant": "Right",
        "connections": "Many",
        "flourish": "Loop",
        "legibility": "Moderate",
        "spacing": "Tight", "letter_shapes": "Rounded",
        "baseline": "Rising", "stroke_variation": "Some taper",
        "signature_visible": True,
    }
    assert parse_report(json.dumps(report)).flourish == "Loop"
    report["slant"] = ""
    with pytest.raises(ValueError):
        parse_report(json.dumps(report))


def test_rejects_unrecognizable_portrait_without_fake_traits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_face(*args: object) -> None:
        raise NoVisibleFaceError("No clearly visible face")
    monkeypatch.setattr(main, "analyze_portrait_detailed", no_face)
    response = client.post(
        "/api/analyze-photo",
        data={"api_key": "test", "language": "he"},
        files={"image": ("portrait.png", picture(), "image/png")},
    )
    assert response.status_code == 422


def test_rejects_image_without_a_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def no_signature(*args: object) -> None:
        raise NoVisibleSignatureError("No recognizable signature")
    monkeypatch.setattr(main, "analyze_signature", no_signature)
    response = client.post(
        "/api/analyze-signature",
        data={"api_key": "test", "language": "he"},
        files={"image": ("signature.png", picture(), "image/png")},
    )
    assert response.status_code == 422


def test_cannot_accept_fake_portrait_evidence() -> None:
    import json
    from dataclasses import asdict
    payload = {
        "face_visible": True,
        "visual_summary": "Friendly-looking photograph",
        "visual_cues": ["Visible smile", "Raised eyebrows"],
        "character_vibe": "Lively character",
        "scores": asdict(PortraitStyle()),
    }
    assert parse_reading(json.dumps(payload)).style.joy == .5
    payload["visual_cues"] = ["Only one"]
    with pytest.raises(ValueError):
        parse_reading(json.dumps(payload))
    payload["face_visible"] = False
    with pytest.raises(NoVisibleFaceError):
        parse_reading(json.dumps(payload))


def test_rejects_model_claim_when_signature_is_absent() -> None:
    import json
    report = {
        "description": "", "impression": "", "line_pressure": "",
        "rhythm": "", "slant": "", "connections": "", "flourish": "",
        "legibility": "", "spacing": "", "letter_shapes": "",
        "baseline": "", "stroke_variation": "", "signature_visible": False,
    }
    with pytest.raises(NoVisibleSignatureError):
        parse_report(json.dumps(report))
