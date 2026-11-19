# Sig-Nature

Turn a name and a portrait into a playful handwritten signature and a video of
a blue ballpoint pen writing that **exact same continuous stroke**.

## Running locally

Requirements: Python 3.12+, FFmpeg with libx264, and an OpenAI API key belonging
to the user. No Node server, database, or GitHub Actions are needed.

```sh
python -m pip install -r requirements.txt
python -m uvicorn backend.main:app --reload
```

Open **http://127.0.0.1:8000**. Supply a Hebrew or Latin full name, a JPEG,
PNG or WebP portrait and your own OpenAI API key. Select Hebrew/English in the
interface. It returns a transparent **signature.png** and a **signature.mp4**
(H.264, yuv420p, 24 FPS, 36 frames, 1.5 seconds).

## Architecture

1. `portrait_analysis.py` - OpenAI vision produces 18 scores for the **visual
   expression and theatrical character** conveyed by the photograph (smiling,
   tense, tough, cute, playful, elegant, etc.). The scores are artistic
   impressions, not personality assessments.
2. `style_mapping.py` - These scores control pressure, stroke roundness,
   slant, irregularity, width, height, letter spacing, writing rhythm,
   directional rise and finishing flourish.
3. `signature_planner.py` - Selects Hebrew Noto font geometry or the original
   experimental Latin path.
4. `font_signature.py` - Renders actual **Noto Sans Hebrew** glyph shapes at
   a photo-dependent width, height, shear, weight and baseline. Morphological
   thinning extracts each glyph's centerline, then a graph traversal produces
   one continuous pen-down route. Fine visible connectors join otherwise
   disconnected components, letters, and words. The original legible font
   silhouettes are retained as the rasterization mask.
5. `pen_path.py` - Renders an exact distance-based prefix at every video frame.
   For Hebrew, every animation frame reveals only the portion of the Noto
   glyph mask visited by the pen; ink pressure and simulated paper indentation
   are independent. Latin uses the original single-stroke renderer.
   The pen nib stays at the current final path point. PNG uses the same path.
6. `animation.py` - Encodes exactly 36 numbered frames with FFmpeg to an
   MP4 encoded as H.264, yuv420p, with faststart.
7. `service.py` - Calls portrait analysis, renders files to a temporary
   directory, then atomically publishes the PNG/MP4 pair. Raw photos and API
   keys are not saved. Only generated results persist in `backend/generated/`
   (ignored by git).

The Hebrew path preserves recognizable font letterforms rather than freehand
symbol sketches. It is still an artistic approximation of handwriting, not a
trained signature model. **The pen never lifts**. Thin visible connectors are
necessary whenever font letters contain separate strokes. Latin glyphs still
use the earlier experimental geometry.

### Font licensing and first-run setup

Hebrew signatures use **Noto Sans Hebrew**, copyright 2022 The Noto Project
Authors, under [SIL OFL 1.1](https://github.com/google/fonts/blob/main/ofl/notosanshebrew/OFL.txt).
No font binaries are committed to Sig-Nature. On machines without the font,
the backend downloads the upstream Google Fonts variable TTF once into
`~/.cache/sig-nature/`. To bypass automatic download, install Noto Sans Hebrew
locally and set `SIG_NATURE_HEBREW_FONT` to its absolute `.ttf` path.
Windows 10 is supported; no Node runtime is required to run the app.


## Tests

Run locally without triggering GitHub Actions:

```sh
python -m pytest -q
node --test tests/frontend.test.mjs
```

The integration tests mock the external vision API; they do not spend API
credits. The MP4 integration test requires local FFmpeg.
