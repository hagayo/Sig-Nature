"""Art-directed portrait analysis. The output controls signature geometry.

Scores describe what a *fictional character* in the photo looks like, not
the subject's real personality or psychological state.
"""
from __future__ import annotations

import base64
from dataclasses import dataclass, fields
from io import BytesIO
import json
import math

import httpx
from PIL import Image, UnidentifiedImageError

MODEL = "gpt-4.1-mini"
MAX_IMAGE_BYTES = 8 * 1024 * 1024
PROMPT = (
    "You are an art director designing a playful fictional handwritten signature "
    "inspired by the person in this photograph. Score the VISIBLE facial expression, "
    "pose, clothing and cinematic atmosphere. These are creative impressions, not "
    "claims about the person's true feelings or character. In particular, "
    "'villainous' means a theatrical, dramatic character look; 'cute', 'tough' "
    "and 'friendly' are stylistic impressions. Each score is a number from 0 to 1. "
    "Different facial expressions should lead to meaningfully different scores. "
    "Assess: joy, sadness, anger, tension, calm, cute, tough, villainous, friendly, "
    "playful, elegance, energy, confidence, shyness, dramatic, head_tilt, "
    "softness, lighting_contrast. If uncertain use 0.5. Return only the JSON object."
)


@dataclass(frozen=True)
class PortraitStyle:
    """Visible expression and visual aesthetic, all scores in the range [0,1]."""
    joy: float = 0.5
    sadness: float = 0.5
    anger: float = 0.5
    tension: float = 0.5
    calm: float = 0.5
    cute: float = 0.5
    tough: float = 0.5
    villainous: float = 0.5
    friendly: float = 0.5
    playful: float = 0.5
    elegance: float = 0.5
    energy: float = 0.5
    confidence: float = 0.5
    shyness: float = 0.5
    dramatic: float = 0.5
    head_tilt: float = 0.5
    softness: float = 0.5
    lighting_contrast: float = 0.5


def parse_style(text: str) -> PortraitStyle:
    """Reject missing, non-numeric, NaN and out-of-range model scores."""
    obj = json.loads(text)
    keys = {field.name for field in fields(PortraitStyle)}
    if not isinstance(obj, dict) or set(obj) != keys:
        raise ValueError("Portrait analysis has missing or unexpected scores")
    values = {}
    for key in keys:
        value = obj[key]
        if isinstance(value, bool) or not isinstance(value, (float, int)):
            raise ValueError(f"Invalid portrait score: {key}")
        if not math.isfinite(value) or not 0 <= value <= 1:
            raise ValueError(f"Out-of-range portrait score: {key}")
        values[key] = float(value)
    return PortraitStyle(**values)


def validate_portrait(portrait: bytes) -> str:
    """Verify actual image bytes, format, dimensions and a strict size ceiling."""
    if not portrait or len(portrait) > MAX_IMAGE_BYTES:
        raise ValueError("Image is empty or exceeds 8 MB")
    try:
        with Image.open(BytesIO(portrait)) as image:
            if image.format not in {"JPEG", "PNG", "WEBP"}:
                raise ValueError("Upload JPEG, PNG or WebP")
            if image.width < 32 or image.height < 32:
                raise ValueError("Image is too small")
            if image.width * image.height > 20_000_000:
                raise ValueError("Image dimensions are too large")
            mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[image.format]
            image.verify()
            return mime
    except (OSError, UnidentifiedImageError) as exc:
        raise ValueError("Invalid image contents") from exc


async def analyze_portrait(portrait: bytes, api_key: str) -> PortraitStyle:
    """Analyze the photo with the user's transient OpenAI API key."""
    mime = validate_portrait(portrait)
    if not api_key.strip():
        raise ValueError("OpenAI API key is required")
    keys = [field.name for field in fields(PortraitStyle)]
    schema = {
        "type": "object",
        "properties": {key: {"type": "number"} for key in keys},
        "required": keys,
        "additionalProperties": False,
    }
    body = {
        "model": MODEL,
        "temperature": 0,
        "max_output_tokens": 600,
        "text": {"format": {
            "type": "json_schema", "name": "portrait_signature_style",
            "strict": True, "schema": schema,
        }},
        "input": [{"role": "user", "content": [
            {"type": "input_text", "text": PROMPT},
            {"type": "input_image", "image_url":
                f"data:{mime};base64,{base64.b64encode(portrait).decode('ascii')}",
             "detail": "high"},
        ]}],
    }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(
            "https://api.openai.com/v1/responses",
            json=body, headers={"Authorization": f"Bearer {api_key.strip()}"},
        )
        response.raise_for_status()
    payload = response.json()
    chunks = [
        part["text"]
        for entry in payload.get("output", [])
        for part in entry.get("content", [])
        if part.get("type") == "output_text" and isinstance(part.get("text"), str)
    ]
    if not chunks:
        raise ValueError("Portrait analysis returned no JSON")
    return parse_style("".join(chunks))
