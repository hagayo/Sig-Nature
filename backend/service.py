"""Production generation: portrait analysis -> handwriting -> rendered assets."""
import asyncio
import os
import re
import time
from functools import lru_cache
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from backend.portrait_analysis import analyze_portrait, validate_portrait
from backend.preview import generate_preview
from backend.signature_planner import validate_name
from backend.name_rules import prepare_name
from backend.style_mapping import style_from_portrait

ASSET_DIR = Path(__file__).resolve().parent / "generated"
ASSET_ID = re.compile(r"^[0-9a-f]{32}$")


def purge_expired_assets(directory: Path, now: float | None = None) -> int:
    """Optionally expire only completed asset folders. Off unless configured.

    A positive SIG_NATURE_ASSET_TTL_HOURS enables cleanup on the next
    generation request, not a background job. Active staging folders and
    unrelated files are deliberately never touched.
    """
    raw = os.environ.get("SIG_NATURE_ASSET_TTL_HOURS")
    if raw is None:
        return 0
    try:
        hours = float(raw)
    except ValueError as exc:
        raise RuntimeError("Invalid asset retention configuration") from exc
    from math import isfinite
    if not isfinite(hours) or hours <= 0:
        raise RuntimeError("Asset retention hours must be positive and finite")
    cutoff = (time.time() if now is None else now) - hours * 3600
    if not directory.is_dir():
        return 0
    removed = 0
    for entry in directory.iterdir():
        if (not ASSET_ID.fullmatch(entry.name)
                or entry.is_symlink() or not entry.is_dir()):
            continue
        try:
            if entry.stat().st_mtime < cutoff:
                shutil.rmtree(entry)
                removed += 1
        except FileNotFoundError:
            continue  # Another request has already cleaned this entry.
    return removed



@lru_cache(maxsize=1)
def ensure_video_encoder() -> None:
    """Validate H.264 output capability before using paid vision credits."""
    executable = shutil.which("ffmpeg")
    if not executable:
        raise FileNotFoundError("FFmpeg is not installed")
    result = subprocess.run(
        [executable, "-hide_banner", "-encoders"],
        capture_output=True, text=True, check=True, timeout=12,
    )
    if "libx264" not in result.stdout:
        raise RuntimeError("FFmpeg does not include the libx264 encoder")


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
    normalized_name, _ = validate_name(full_name)
    name = prepare_name(normalized_name)
    # Preflight local dependencies BEFORE using the user's paid OpenAI credits.
    # Both checks run outside the asynchronous server event loop.
    await asyncio.to_thread(ensure_video_encoder)
    # A missing photographic plate must fail before the paid vision request.
    from backend.cinematic_video import validate_cinematic_materials
    await asyncio.to_thread(validate_cinematic_materials)
    from backend.font_signature import get_font
    for script in {run.script for run in name.runs}:
        await asyncio.to_thread(get_font, 64, None, script)
    await asyncio.to_thread(purge_expired_assets, ASSET_DIR)
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
