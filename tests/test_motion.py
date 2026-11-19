"""Regression tests for dynamic pen speed, natural curves and route continuity."""
from math import hypot, isclose

import pytest

from backend.motion import FRAME_RATE, MotionTimeline
from backend.pen_path import PenPath
from backend.stroke_route import route_skeleton


def test_motion_60fps_duration_follows_complexity() -> None:
    short = PenPath(((20,30),(200,30)),tempo=.5)
    long = PenPath(tuple((float(x), 120. + 20.*(x//100)%2)
                         for x in range(20,700,3)),tempo=.5)
    a,b = MotionTimeline(short),MotionTimeline(long)
    assert FRAME_RATE == 60
    assert a.frame_count > 36
    assert b.frame_count > a.frame_count
    assert 5.1 <= a.writing_seconds <= 9.0
    assert b.duration > b.writing_seconds


def test_motion_clamps_final_position_and_keeps_exact_path() -> None:
    points=((30.,35.),(320.,35.),(320.,100.),(510.,130.))
    path=PenPath(points,(.2,.7,.8,.4),tempo=.6)
    motion=MotionTimeline(path)
    assert motion.at(0.).progress == 0.
    assert motion.at(motion.writing_seconds).progress == 1.
    assert motion.at(motion.duration).position == points[-1]
    assert motion.at(-10.).position == points[0]
    assert motion.at(motion.duration).velocity == 0
    progress=[motion.at(index / FRAME_RATE).progress
              for index in range(motion.frame_count)]
    assert progress==sorted(progress)
    assert isclose(progress[-1],1)


def test_corners_reduce_speed_without_pen_lifts() -> None:
    points=[(float(x),200.) for x in range(30,331,5)]
    points.extend((330.,float(y)) for y in range(205,406,5))
    path=PenPath(tuple(points),tempo=.5)
    motion=MotionTimeline(path)
    straight=motion.at(motion.times[15]).velocity
    corner=motion.at(motion.times[60]).velocity
    assert corner < straight
    assert all(motion.times[i+1]>motion.times[i]
               for i in range(len(motion.times)-1))


def test_invalid_times_rejected() -> None:
    motion=MotionTimeline(PenPath(((5,5),(50,50))))
    with pytest.raises(ValueError):
        motion.at(float("nan"))


def test_glyph_route_covers_ink_and_never_teleports() -> None:
    skeleton={(x,40) for x in range(20,91)}
    skeleton |= {(55,y) for y in range(18,65)}
    route=route_skeleton(skeleton)
    assert set(skeleton).issubset(set(route))
    assert all(hypot(b[0]-a[0],b[1]-a[1])<=2
               for a,b in zip(route,route[1:]))
    assert route[0][0]>=route[-1][0]


def test_disconnected_glyph_parts_are_visibly_connected() -> None:
    skeleton={(x,10) for x in range(20,30)}
    skeleton |= {(x,10) for x in range(45,55)}
    route=route_skeleton(skeleton)
    assert set(skeleton).issubset(set(route))
    # The bridge is deliberately a continuous visible line.
    assert any(hypot(b[0]-a[0],b[1]-a[1]) > 2
               for a,b in zip(route,route[1:]))


def test_complex_signature_has_human_scale_pacing() -> None:
    # Long handwriting should no longer be rushed into a 3-second stroke.
    import math
    points = tuple(
        (400. - i*1.3, 350. + 18.*math.sin(i*.075))
        for i in range(350)
    )
    path = PenPath(points, tempo=.5)
    motion = MotionTimeline(path)
    assert motion.writing_seconds >= 5.5
    assert 5.5 < motion.duration <= 10.7
    assert all(b > a for a, b in zip(motion.times, motion.times[1:]))


def test_distance_aware_timing_stable_under_point_resampling() -> None:
    # Densifying a straight stroke must not change its duration materially.
    coarse = PenPath(tuple((float(x), 100.) for x in range(50, 551, 5)))
    fine = PenPath(tuple((float(x), 100.) for x in range(50, 551)))
    a, b = MotionTimeline(coarse), MotionTimeline(fine)
    assert abs(a.writing_seconds-b.writing_seconds) < .05
    assert abs(a.at(a.writing_seconds*.5).progress-.5) < .1
    assert abs(b.at(b.writing_seconds*.5).progress-.5) < .1
