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

All OpenAI calls are made with the API key entered for that request. The key and the input portrait/signature are **not saved** by the backend. Generated PNG/MP4 files are kept in `backend/generated/`, excluded from git. By default they persist until manually deleted. Optionally set `SIG_NATURE_ASSET_TTL_HOURS` to a positive number to remove expired completed results on the next generation request. Staging folders and unrelated files are never touched; this is opt-in, not a background scheduler. Expired download links stop working.

## Handwriting engine

**Hebrew:** `backend/font_signature.py` derives handwriting from the open-source [Gveret Levin](https://github.com/AlefAlefAlef/gveret-levin) font by AlefAlefAlef, SIL Open Font License 1.1. Noto Sans Hebrew is no longer the basis for signatures. The font is not bundled. The backend downloads the upstream TTF once and caches it at `~/.cache/sig-nature/GveretLevin-Regular.ttf`; alternatively set `SIG_NATURE_HEBREW_FONT` to a local TTF path.

The handwriting engine rasterizes real cursive letterforms, skeletonizes them, finds an ordered pen-down walk, joins otherwise disjoint components with visible pen strokes and finishes with a drawn flourish. Curved connectors follow glyph endpoints rather than using uniform straight bridges. Each photo influences letter width, height, slant, spacing, roundness, baseline, pressure, writing tempo and finishing gesture. Pressure now modulates stroke thickness and ink darkness throughout the handwritten letters, not only the simulated paper indentation. The same trajectory drives the animation and final PNG, with the raster artwork restricted to nib-traced ink to prevent a last-frame reveal of untraced lines.

**Latin:** The existing single-stroke prototype continues to support Latin names.

**Video:** 36 progressive frames, H.264 MP4, 24 FPS, 1.5 seconds. The pen nib remains positioned at the current path endpoint. Paper indentation and pressure shading are decorative. No invisible pen-lift moves are used.

The handwritten font shapes and algorithmic one-stroke routing are an **artistic approximation**, not an exact simulation of how every human would physically write. Disconnected Hebrew glyph strokes necessarily acquire visible connecting ink lines to satisfy the single-contact requirement.

## Analysis API

- `POST /api/generate`: multipart `full_name`, `portrait`, `api_key` - returns `signature_png_url`, `animation_mp4_url`.
- `POST /api/analyze-photo`: multipart `image`, `api_key`, `language` (`he`/`en`). Returns `summary`, `cues` (2-5 concrete visible clues), `vibe`, `traits` (18 calibrated values), and `writing_style` (the exact geometry controls used by generation). The photo preview uses EXIF-normalized, resized JPEG; the generated signature uses the same 18-score visual model.
- `POST /api/analyze-signature`: multipart `image`, `api_key`, `language`. Returns a concise `analysis` of visible strokes and a playful character impression. Fine ink remains intact through a white-composited PNG upload. The analysis separates line appearance from actual writing pressure, and does not hallucinate a person's name.
- Both analysis routes reject an unrecognizable image with HTTP 422. A malformed, refused or incomplete structured vision response returns 502, and provider errors are mapped separately. Prompts and JSON schemas live in `backend/portrait_analysis.py` and `backend/signature_analysis.py`; both use `backend/vision_client.py` for identical OpenAI request handling.

Descriptions of personality and emotion are **creative impressions of an image**, not factual measurements.

## No-API visual QA

Use the deterministic four-style contact sheet to assess handwriting readability
and individuality without sending images, spending OpenAI credits or running CI:

```sh
python -m scripts.preview_styles --name "חגי און" --output signature-preview.png
```

The command writes four isolated transparent PNGs and a 2-by-2 comparison
image. Use `--font C:/path/to/GveretLevin-Regular.ttf` when offline. It is a
visual inspection tool, not a claim that human handwriting realism is solved.

## Local tests (do not trigger GitHub Actions)

```sh
python -m pytest -q
node --test tests/*.test.mjs
```

External OpenAI calls are mocked in the tests, so no API credits are spent. FFmpeg is needed for the local MP4 pipeline test. The old GitHub workflow remains parked in `ci-disabled/ci.yml`; no workflows are active under `.github/workflows/`.
