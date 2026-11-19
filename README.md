# Sig-Nature

A playful portrait-inspired signature maker, plus two stand-alone analysis tools.

## Pages

- `/` - Create a signature from a full name, a portrait and your own OpenAI API key. Download the exact same result as a transparent PNG and a video.
- `/analyze-photo.html` - Inspect the visual impressions identified in a portrait and all numeric handwriting parameters derived from them, for debugging.
- `/analyze-signature.html` - Upload an existing handwritten signature and get a playful visual interpretation of its strokes and style.

All three pages use **the same** `style.css` and `script.js`, one navigation/header design, responsive layout, and a Hebrew/English toggle. CSS uses shared `:root` color, spacing, radius and button tokens.

## Local setup (Windows 10 or Linux)

Requirements: Python 3.12+, FFmpeg with `libx264`, internet access, and a personal OpenAI API key.

```sh
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

Open http://127.0.0.1:8000.

All OpenAI calls are made with the API key entered for that request. The key and the input portrait/signature are **not saved** by the backend. Generated PNG/MP4 files are kept in `backend/generated/`, which is excluded from git. This local MVP has no automatic retention cleanup; remove old results manually.

## Handwriting engine

**Hebrew:** `backend/font_signature.py` derives handwriting from the open-source [Gveret Levin](https://github.com/AlefAlefAlef/gveret-levin) font by AlefAlefAlef, SIL Open Font License 1.1. Noto Sans Hebrew is no longer the basis for signatures. The font is not bundled. The backend downloads the upstream TTF once and caches it at `~/.cache/sig-nature/GveretLevin-Regular.ttf`; alternatively set `SIG_NATURE_HEBREW_FONT` to a local TTF path.

The handwriting engine rasterizes real cursive letterforms, skeletonizes them, finds an ordered pen-down walk, joins otherwise disjoint components with visible pen strokes and finishes with a drawn flourish. Curved connectors follow glyph endpoints rather than using uniform straight bridges. Each photo influences letter width, height, slant, spacing, roundness, baseline, pressure, writing tempo and finishing gesture. The same trajectory drives the animation and final PNG.

**Latin:** The existing single-stroke prototype continues to support Latin names.

**Video:** 36 progressive frames, H.264 MP4, 24 FPS, 1.5 seconds. The pen nib remains positioned at the current path endpoint. Paper indentation and pressure shading are decorative. No invisible pen-lift moves are used.

The handwritten font shapes and algorithmic one-stroke routing are an **artistic approximation**, not an exact simulation of how every human would physically write. Disconnected Hebrew glyph strokes necessarily acquire visible connecting ink lines to satisfy the single-contact requirement.

## Analysis API

- `POST /api/generate`: multipart `full_name`, `portrait`, `api_key` - returns `signature_png_url`, `animation_mp4_url`.
- `POST /api/analyze-photo`: multipart `image`, `api_key`, `language` (`he`/`en`) - returns `traits` and `writing_style` exactly as used by generation.
- `POST /api/analyze-signature`: multipart `image`, `api_key`, `language` - returns a narrative interpretation and visible features of the uploaded signature.

Descriptions of personality and emotion are **creative impressions of an image**, not factual measurements.

## Local tests (do not trigger GitHub Actions)

```sh
python -m pytest -q
node --test tests/*.test.mjs
```

External OpenAI calls are mocked in the tests, so no API credits are spent. FFmpeg is needed for the local MP4 pipeline test. The old GitHub workflow remains parked in `ci-disabled/ci.yml`; no workflows are active under `.github/workflows/`.
