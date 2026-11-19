"""Analyze visible portrait expression and composition for signature styling.

This module describes observable visual cues, not the person's true feelings
or psychological traits. User-supplied API keys are used only for the request.
"""

import base64
from dataclasses import dataclass
import json

import httpx

MODEL = "gpt-4.1-mini"
PROMPT = (
    "Describe only VISIBLE features of the portrait, without inferring inner "
    "emotions, personality, identity, or sensitive traits. Return ONLY a JSON "
    "object with numeric values in [0,1] for these keys: "
    "smile (visible smile intensity), mouth_open, eyebrow_raise, "
    "head_tilt (absolute visible tilt), visual_energy (apparent dynamism "
    "of pose and composition), softness (softness of visible expression "
    "and lighting). Use 0.5 if a feature is uncertain. No other keys."
)
KEYS = ("smile", "mouth_open", "eyebrow_raise", "head_tilt", "visual_energy", "softness")


@dataclass(frozen=True)
class PortraitStyle:
    """Observable portrait cues, normalized to [0,1]."""

    smile: float = 0.5
    mouth_open: float = 0.5
    eyebrow_raise: float = 0.5
    head_tilt: float = 0.5
    visual_energy: float = 0.5
    softness: float = 0.5


def parse_style(text: str) -> PortraitStyle:
    """Validate model JSON strictly before using it for geometry."""
    payload = json.loads(text)
    if not isinstance(payload, dict) or set(payload) != set(KEYS):
        raise ValueError("Invalid portrait analysis fields")
    values = {}
    for key in KEYS:
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ValueError(f"Invalid portrait style value: {key}")
        if not 0 <= value <= 1:
            raise ValueError(f"Out-of-range portrait style value: {key}")
        values[key] = float(value)
    return PortraitStyle(**values)


async def analyze_portrait(portrait: bytes, api_key: str) -> PortraitStyle:
    """Use the user's OpenAI API key for one vision request."""
    if not portrait or not api_key.strip():
        raise ValueError("Portrait and API key are required")
    if len(portrait) > 8 * 1024 * 1024:
        raise ValueError("Portrait exceeds 8 MB")
    # JPEG, PNG and WebP are supported as data URLs.
    if portrait.startswith(b"\\xff\\xd8\\xff"):
        mime = "image/jpeg"
    elif portrait.startswith(b"\\x89PNG\\r\\n\\x1a\\n"):
        mime = "image/png"
    elif portrait[:4] == b"RIFF" and portrait[8:12] == b"WEBP":
        mime = "image/webp"
    else:
        raise ValueError("Unsupported portrait format")
    image_url = f"data:{mime};base64,{base64.b64encode(portrait).decode('ascii')}"
    body = {
        "model": MODEL,
        "input": [{
            "role": "user",
            "content": [
                {"type": "input_text", "text": PROMPT},
                {"type": "input_image", "image_url": image_url, "detail": "low"},
            ],
        }],
        "max_output_tokens": 200,
    }
    async with httpx.AsyncClient(timeout=45) as client:
        response = await client.post(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {api_key}"},
            json=body,
        )
        response.raise_for_status()
    result = response.json()
    chunks = [
        part["text"]
        for output in result.get("output", [])
        for part in output.get("content", [])
        if part.get("type") == "output_text" and isinstance(part.get("text"), str)
    ]
    if not chunks:
        raise ValueError("Vision model returned no portrait analysis")
    return parse_style("".join(chunks))
