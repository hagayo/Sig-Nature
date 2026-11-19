"""Photo-plate and ink-contact quality contracts without an OpenAI key."""
from math import hypot
from pathlib import Path
import shutil
import subprocess

import numpy as np
import pytest
from PIL import Image, ImageDraw

from backend.cinematic_video import (
    OUTPUT_SIZE, PAPER_FORESHORTEN, REVEAL_SECONDS,
    _Ink, _assets, _field_transform, _photo_sprite,
    cinematic_frames, encode_cinematic_video, validate_cinematic_materials,
)
from backend.motion import FRAME_RATE, MotionTimeline


class SimplePath:
    """A deterministic, reproducible pen-down fixture."""
    points = tuple((float(75 + i * 3), float(260 + 22 * np.sin(i * .08)))
                   for i in range(120))
    pressures = tuple(.55 for _ in points)
    tempo = .5
    artwork = None
    reveal_width = 4

    def trace(self, fraction: float):
        target = float(fraction) * self.length
        remaining = target
        result = [(self.points[0], self.pressures[0])]
        for a, b in zip(self.points, self.points[1:]):
            dist = hypot(b[0] - a[0], b[1] - a[1])
            if remaining >= dist:
                result.append((b, .55))
                remaining -= dist
            else:
                u = remaining / dist
                result.append(((a[0] * (1-u) + b[0]*u,
                                a[1] * (1-u) + b[1]*u), .55))
                break
        return tuple(result)

    @property
    def length(self):
        return sum(hypot(b[0]-a[0],b[1]-a[1])
                   for a,b in zip(self.points,self.points[1:]))


def test_no_top_down_vector_pen_is_rendered():
    validate_cinematic_materials()
    photo, paper = _assets()
    assert photo.ndim == 3 and photo.shape[2] == 4
    assert paper.shape[2] == 3
    assert photo[:,:,3].min() == 0
    assert photo[:,:,3].max() > 200
    assert photo.shape[0] > 300
    sprite, anchor = _photo_sprite()
    assert sprite.shape[2] == 4
    assert anchor[0] > 200 and anchor[1] > 600


def test_camera_looks_from_side_and_tracks_nib():
    matrix = _field_transform((360, 360), 2.65)
    assert matrix.shape == (2,3)
    assert abs(matrix[1,1] / matrix[0,0] - PAPER_FORESHORTEN) < .001
    assert abs(matrix[0,1]) > .1
    x = matrix[0,0]*360 + matrix[0,1]*360 + matrix[0,2]
    y = matrix[1,1]*360 + matrix[1,2]
    assert 0 < x < OUTPUT_SIZE[0] and 0 < y < OUTPUT_SIZE[1]


def test_pen_deposits_ink_only_where_nib_has_visited():
    art = Image.new('L',(720,720),0)
    d = ImageDraw.Draw(art)
    d.line((50,200,650,200),fill=255,width=6)
    d.line((50,390,650,390),fill=255,width=6)
    class PathFixture:
        points = ((50.,200.),(650.,200.))
        pressures = (.5,.5)
        artwork = art
        reveal_width = 9
    ink = _Ink(PathFixture(),(720,720))
    before = ink.advance(.35)
    assert before[400,105] > 0
    assert before[400,1000] == 0
    after = ink.advance(1.0)
    assert after[400,1050] > 0
    assert after[780,1050] == 0
    with pytest.raises(ValueError,match='backwards'):
        ink.advance(.2)


def test_cinematic_frames_are_photographic_and_full_hd():
    path = SimplePath()
    frames = cinematic_frames(path)
    image = next(frames)
    assert image.shape == (720,1280,3)
    assert image.dtype == np.uint8
    assert image.std() > 10  # Camera contains actual pen, not flat empty art.
    assert image[150,950].mean() != image[650,100].mean()
    assert REVEAL_SECONDS >= 1.0


@pytest.mark.skipif(shutil.which('ffmpeg') is None,reason='FFmpeg unavailable')
def test_full_cinematic_video_has_clean_h264_frames(tmp_path:Path):
    output = tmp_path / 'cinema.mp4'
    encode_cinematic_video(SimplePath(), output)
    assert output.stat().st_size > 50000
    if shutil.which('ffprobe'):
        raw = subprocess.check_output([
            'ffprobe','-v','error','-select_streams','v:0',
            '-show_entries','stream=codec_name,width,height,avg_frame_rate,nb_frames',
            '-of','default=noprint_wrappers=1',str(output)],text=True)
        assert 'codec_name=h264' in raw
        assert 'width=1280' in raw and 'height=720' in raw
        assert 'avg_frame_rate=60/1' in raw
        frames = int(next(v.split('=')[1] for v in raw.splitlines()
                          if v.startswith('nb_frames=')))
        assert frames == int(np.ceil((MotionTimeline(SimplePath()).writing_seconds
                                      + REVEAL_SECONDS) * FRAME_RATE))


def test_macro_camera_has_natural_inertia():
    from backend.cinematic_video import CinematicCamera
    path = SimplePath()
    camera = CinematicCamera(path)
    start = camera.center.copy()
    target = (float(start[0]-100), float(start[1]+40))
    camera.transform(target, 0.)
    # The camera must not snap directly to the nib on every frame.
    assert 0 < abs(camera.center[0] - start[0]) < 30
    assert 0 < abs(camera.center[1] - start[1]) < 15
    assert REVEAL_SECONDS >= 1.5
