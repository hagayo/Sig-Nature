"""Production generation: portrait analysis -> handwriting -> rendered assets."""
import asyncio
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from backend.portrait_analysis import analyze_portrait, validate_portrait
from backend.preview import generate_preview
from backend.signature_planner import plan_signature
from backend.style_mapping import style_from_portrait

ASSET_DIR = Path(__file__).resolve().parent / "generated"


@dataclass(frozen=True)
class GeneratedAssets:
    """Identifier for an existing, validated PNG and MP4 asset pair."""
    asset_id: str


async def generate_signature(
    full_name: str,
    portrait: bytes,
    api_key: str,
) -> GeneratedAssets:
    """Generate photo-specific ink and video; do not store photo or API key."""
    validate_portrait(portrait)
    plan_signature(full_name)  # Reject unsupported names before a paid API call.
    impression = await analyze_portrait(portrait, api_key)
    handwriting = style_from_portrait(impression)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    identifier = uuid4().hex
    # Staging directory ensures clients never see partially generated media.
    with TemporaryDirectory(prefix="_building_", dir=ASSET_DIR) as directory:
        staging = Path(directory)
        png, mp4 = await asyncio.to_thread(
            generate_preview, full_name, staging, portrait, handwriting
        )
        if not png.is_file() or not mp4.is_file() or mp4.stat().st_size == 0:
            raise RuntimeError("Generated assets are missing")
        staging.rename(ASSET_DIR / identifier)
    return GeneratedAssets(identifier)
