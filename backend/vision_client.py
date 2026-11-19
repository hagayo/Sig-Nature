"""Shared OpenAI vision transport for the two analysis routes.

Only validated image bytes and the current request's API key leave this function.
Responses are schema-constrained, checked for truncation and never logged.
"""
from __future__ import annotations

import base64
import httpx

ENDPOINT = "https://api.openai.com/v1/responses"
MODEL = "gpt-4.1-mini"


class VisionResponseError(ValueError):
    """The model returned an incomplete, refused, or malformed response."""


async def request_vision(
    picture: bytes,
    mime: str,
    key: str,
    instructions: str,
    schema_name: str,
    schema: dict,
    *,
    max_output_tokens: int = 1300,
) -> str:
    if not key.strip():
        raise ValueError("OpenAI API key is required")
    if mime not in {"image/jpeg", "image/png", "image/webp"} or not picture:
        raise ValueError("Invalid image payload")
    body = {
        "model": MODEL,
        "temperature": 0,
        "max_output_tokens": max_output_tokens,
        "text": {"format": {
            "type": "json_schema",
            "name": schema_name,
            "strict": True,
            "schema": schema,
        }},
        "input": [{"role": "user", "content": [
            {"type": "input_text", "text": instructions},
            {"type": "input_image",
             "image_url": f"data:{mime};base64,{base64.b64encode(picture).decode('ascii')}",
             "detail": "high"},
        ]}],
    }
    async with httpx.AsyncClient(timeout=75) as client:
        response = await client.post(
            ENDPOINT,
            headers={"Authorization": f"Bearer {key.strip()}"},
            json=body,
        )
        response.raise_for_status()
    data = response.json()
    if data.get("status") not in (None, "completed"):
        raise VisionResponseError("Analysis was not completed")
    parts = [
        part for item in data.get("output", [])
        for part in item.get("content", [])
    ]
    if any(part.get("type") == "refusal" for part in parts):
        raise VisionResponseError("Analysis was refused")
    result = "".join(
        part["text"] for part in parts
        if part.get("type") == "output_text" and isinstance(part.get("text"), str)
    )
    if not result.strip():
        raise VisionResponseError("Analysis did not produce valid structured text")
    return result
