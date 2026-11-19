"""Mocked contract test for shared structured OpenAI vision calls."""
import asyncio
from dataclasses import asdict
from io import BytesIO
import json

import httpx
from PIL import Image
import pytest

from backend import vision_client
from backend.portrait_analysis import (
    PortraitStyle, analyze_portrait, analyze_portrait_detailed,
    portrait_schema,
)


def portrait_png() -> bytes:
    picture = BytesIO()
    Image.new("RGB", (96, 96), "purple").save(picture, "PNG")
    return picture.getvalue()


def test_analyze_portrait_http_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []
    answer = {
        "face_visible": True,
        "visual_summary": "A smiling face with bright lighting",
        "visual_cues": ["Upturned mouth", "Raised eyebrows"],
        "character_vibe": "A lively, playful character",
        "scores": asdict(PortraitStyle(joy=1, sadness=0, tough=0)),
    }

    class DummyClient:
        def __init__(self, **kwargs: object) -> None: pass

        async def __aenter__(self): return self

        async def __aexit__(self, *args: object) -> None: pass

        async def post(self, url: str, *, json: dict, headers: dict) -> httpx.Response:
            calls.append({"url": url, "json": json, "headers": headers})
            return httpx.Response(
                200, request=httpx.Request("POST", url),
                json={"status": "completed", "output": [{
                    "content": [{"type": "output_text", "text": __import__("json").dumps(answer)}]
                }]},
            )

    monkeypatch.setattr(vision_client.httpx, "AsyncClient", DummyClient)
    reading = asyncio.run(analyze_portrait_detailed(portrait_png(), "test-user-key", "en"))
    assert reading.style.joy == 1
    assert len(reading.cues) == 2
    assert reading.summary.startswith("A smiling")
    assert calls[0]["url"] == "https://api.openai.com/v1/responses"
    assert calls[0]["headers"] == {"Authorization": "Bearer test-user-key"}
    body = calls[0]["json"]
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["text"]["format"]["schema"] == portrait_schema()
    assert body["input"][0]["content"][1]["image_url"].startswith("data:image/jpeg;base64,")
    assert "natural English" in body["input"][0]["content"][0]["text"]

    # Generation calls the same analysis and extracts the same trait scores.
    style = asyncio.run(analyze_portrait(portrait_png(), "test-user-key"))
    assert style.joy == reading.style.joy


def test_incomplete_vision_response_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    class IncompleteClient:
        def __init__(self, **kwargs: object) -> None: pass
        async def __aenter__(self): return self
        async def __aexit__(self, *args: object) -> None: pass
        async def post(self, url: str, **kwargs: object) -> httpx.Response:
            return httpx.Response(
                200, request=httpx.Request("POST", url),
                json={"status": "incomplete", "output": []},
            )
    monkeypatch.setattr(vision_client.httpx, "AsyncClient", IncompleteClient)
    with pytest.raises(vision_client.VisionResponseError):
        asyncio.run(analyze_portrait(portrait_png(), "test-key"))
