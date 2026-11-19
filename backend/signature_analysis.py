"""Playful interpretation of visible signature strokes using an OpenAI vision model."""
from __future__ import annotations
import base64
from dataclasses import dataclass
import json

import httpx
from backend.portrait_analysis import MODEL, validate_portrait


@dataclass(frozen=True)
class SignatureReport:
    description: str
    impression: str
    line_pressure: str
    rhythm: str
    slant: str
    connections: str
    flourish: str
    legibility: str

    def to_payload(self) -> dict[str, object]:
        return {
            "description": self.description,
            "impression": self.impression,
            "features": {
                "line_pressure": self.line_pressure,
                "rhythm": self.rhythm,
                "slant": self.slant,
                "connections": self.connections,
                "flourish": self.flourish,
                "legibility": self.legibility,
            }
        }


def parse_report(text: str) -> SignatureReport:
    values = json.loads(text)
    keys = set(SignatureReport.__dataclass_fields__)
    if not isinstance(values, dict) or set(values) != keys:
        raise ValueError("Signature analysis returned unexpected fields")
    if any(not isinstance(v, str) or not v.strip() or len(v) > 600
           for v in values.values()):
        raise ValueError("Signature analysis returned invalid text")
    return SignatureReport(**{key: value.strip() for key, value in values.items()})


async def analyze_signature(image: bytes, api_key: str, language: str = "he") -> SignatureReport:
    """Interpret the signature's visible marks, not the writer's actual psyche."""
    mime = validate_portrait(image)
    if language not in {"he", "en"}:
        raise ValueError("Unsupported language")
    if not api_key.strip():
        raise ValueError("OpenAI API key is required")
    labels = list(SignatureReport.__dataclass_fields__)
    schema = {
        "type": "object",
        "properties": {key: {"type": "string"} for key in labels},
        "required": labels,
        "additionalProperties": False,
    }
    prompt = (
        "Analyze this PHOTO OF A HANDWRITTEN SIGNATURE for a playful creative "
        "graphology-style experience. Describe only the signature's visible "
        "features: strokes, spacing, apparent weight, slant, loops, connections "
        "and legibility. Offer a whimsical fictional character impression in "
        "'impression', phrased as the visual style's vibe, never as a factual "
        "claim about the signer, their identity, feelings, personality, health, "
        "or trustworthiness. Distinguish an apparent thick ink stroke from "
        "actual measured writing pressure. If a property is not visible say so. "
        "Do not invent text or a person's name. "
        f"Answer in {'natural Hebrew' if language == 'he' else 'English'}. "
        "Return a JSON object with strings: description (1-2 sentences about "
        "overall visible style), impression (one playful sentence), "
        "line_pressure (apparent line thickness), rhythm, slant, connections, "
        "flourish, legibility. No preamble."
    )
    body = {
        "model": MODEL,
        "max_output_tokens": 550,
        "text": {"format": {
            "type": "json_schema", "name": "signature_analysis",
            "strict": True, "schema": schema,
        }},
        "input": [{"role": "user", "content": [
            {"type": "input_text", "text": prompt},
            {"type": "input_image",
             "image_url": f"data:{mime};base64,{base64.b64encode(image).decode('ascii')}",
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
    text = "".join(
        block["text"] for item in payload.get("output", [])
        for block in item.get("content", [])
        if block.get("type") == "output_text" and isinstance(block.get("text"), str)
    )
    if not text:
        raise ValueError("No signature interpretation returned")
    return parse_report(text)
