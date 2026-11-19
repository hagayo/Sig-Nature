"""Check user-supplied key and real image are sent to OpenAI Responses."""
import asyncio
from dataclasses import asdict
from io import BytesIO
import json

import httpx
from PIL import Image
import pytest

from backend import portrait_analysis
from backend.portrait_analysis import PortraitStyle


def test_analyze_portrait_http_payload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    picture = BytesIO()
    Image.new("RGB", (96,96), "purple").save(picture, "PNG")
    calls: list[dict[str, object]] = []

    class DummyClient:
        def __init__(self, **kwargs: object) -> None:
            pass

        async def __aenter__(self) -> "DummyClient":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, *, json: dict, headers: dict) -> httpx.Response:
            calls.append({"url":url, "json":json, "headers":headers})
            request = httpx.Request("POST", url)
            data = asdict(PortraitStyle(joy=1, sadness=0, tough=0))
            return httpx.Response(
                200, request=request,
                json={"output":[{"content":[
                    {"type":"output_text","text":__import__("json").dumps(data)}
                ]}]},
            )

    monkeypatch.setattr(portrait_analysis.httpx, "AsyncClient", DummyClient)
    result = asyncio.run(
        portrait_analysis.analyze_portrait(picture.getvalue(), "test-user-key")
    )
    assert result.joy == 1
    assert result.sadness == 0
    assert calls[0]["url"] == "https://api.openai.com/v1/responses"
    assert calls[0]["headers"] == {"Authorization": "Bearer test-user-key"}
    body = calls[0]["json"]
    assert body["text"]["format"]["type"] == "json_schema"
    assert body["input"][0]["content"][1]["image_url"].startswith("data:image/png;base64,")
