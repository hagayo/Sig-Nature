"""Continuous pen geometry, pressure ink and antialiased 60 FPS video frames."""
from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot, isfinite
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from backend.motion import MotionTimeline, FRAME_RATE
from backend.pen_sprite import draw_ballpoint

Point = tuple[float, float]
INK = (25, 42, 115)
SUPERSAMPLE = 2


@dataclass(frozen=True)
class PenPath:
    """One pen-down signature, shared by transparent PNG and the animated video."""
    points: tuple[Point, ...]
    pressures: tuple[float, ...] = ()
    tempo: float = .5
    artwork: Image.Image | None = field(default=None, compare=False, repr=False)
    reveal_width: int = 8

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("Pen path needs at least two points")
        if any(len(p) != 2 or not all(isfinite(v) for v in p) for p in self.points):
            raise ValueError("Pen path contains non-finite coordinates")
        if self.pressures and len(self.pressures) != len(self.points):
            raise ValueError("A pressure value is required for every pen point")
        if any(not isfinite(v) or not 0 <= v <= 1 for v in self.pressures):
            raise ValueError("Invalid pen pressure")
        if not isfinite(self.tempo) or not 0 <= self.tempo <= 1:
            raise ValueError("Invalid writing tempo")
        if not isinstance(self.reveal_width, int) or not 2 <= self.reveal_width <= 24:
            raise ValueError("Invalid ink reveal width")
        if self.length <= 0:
            raise ValueError("Pen path has zero length")

    @property
    def length(self) -> float:
        return sum(hypot(b[0]-a[0], b[1]-a[1])
                   for a,b in zip(self.points,self.points[1:]))

    def trace(self, fraction: float) -> tuple[tuple[Point,float], ...]:
        """Return the exact arc-length prefix with pressure at the live nib."""
        if not isfinite(fraction) or not 0 <= fraction <= 1:
            raise ValueError("Progress must be finite and between 0 and 1")
        pressure = self.pressures or (1.0,)*len(self.points)
        if fraction == 1:
            return tuple(zip(self.points, pressure))
        if fraction == 0:
            return ((self.points[0], pressure[0]),)
        remaining = self.length*fraction
        result = [(self.points[0],pressure[0])]
        for i,(a,b) in enumerate(zip(self.points,self.points[1:])):
            d = hypot(b[0]-a[0],b[1]-a[1])
            if d == 0:
                continue
            if remaining >= d:
                result.append((b,pressure[i+1]))
                remaining -= d
            else:
                alpha=remaining/d
                result.append(((a[0]+(b[0]-a[0])*alpha,
                                a[1]+(b[1]-a[1])*alpha),
                               pressure[i]+(pressure[i+1]-pressure[i])*alpha))
                break
        return tuple(result)

    def prefix(self,fraction:float)->tuple[Point,...]:
        return tuple(point for point,_ in self.trace(fraction))


def _validate_bounds(path:PenPath,size:tuple[int,int])->None:
    if min(size) <= 0:
        raise ValueError("Canvas dimensions must be positive")
    if path.artwork is not None and path.artwork.size != size:
        raise ValueError("Artwork size does not match output canvas")
    if any(not (0 <= x < size[0] and 0 <= y < size[1]) for x,y in path.points):
        raise ValueError("Pen path contains a point outside the canvas")


def _ink_layer(trace:tuple[tuple[Point,float], ...],
               size:tuple[int,int], artwork:Image.Image | None=None,
               reveal_width:int=8, complete:bool=False)->Image.Image:
    """Supersample the exact nib-visited ink. Complete is legacy compatibility."""
    scale=SUPERSAMPLE
    hi=(size[0]*scale,size[1]*scale)
    if artwork is not None:
        mask=Image.new("L",hi,0)
        painter=ImageDraw.Draw(mask)
        if len(trace)>1:
            painter.line([(x*scale,y*scale) for (x,y),_ in trace],
                         fill=255,width=reveal_width*scale,joint="curve")
        r=reveal_width*scale/2
        for x,y in (trace[0][0],trace[-1][0]):
            painter.ellipse((x*scale-r,y*scale-r,x*scale+r,y*scale+r),fill=255)
        cover=mask.resize(size,Image.Resampling.LANCZOS)
        alpha=ImageChops.multiply(artwork,cover)
        result=Image.new("RGBA",size,(*INK,0))
        result.putalpha(alpha)
        return result
    layer=Image.new("RGBA",hi,(0,0,0,0))
    draw=ImageDraw.Draw(layer)
    for (a,pa),(b,pb) in zip(trace,trace[1:]):
        pressure=(pa+pb)*.5
        width=max(1,round((1.35+pressure*4.7)*scale))
        alpha=min(255,round(165+pressure*90))
        ink=(*INK,alpha)
        draw.line(((a[0]*scale,a[1]*scale),(b[0]*scale,b[1]*scale)),
                  fill=ink,width=width,joint="curve")
        radius=width/2
        draw.ellipse((b[0]*scale-radius,b[1]*scale-radius,
                      b[0]*scale+radius,b[1]*scale+radius),fill=ink)
    if len(trace)==1:
        a,_=trace[0]
        draw.ellipse((a[0]*scale-2,a[1]*scale-2,
                      a[0]*scale+2,a[1]*scale+2),fill=(*INK,255))
    return layer.resize(size,Image.Resampling.LANCZOS)


def render_signature(path:PenPath,output:Path,
                     size:tuple[int,int]=(720,720))->Path:
    _validate_bounds(path,size)
    output.parent.mkdir(parents=True,exist_ok=True)
    _ink_layer(path.trace(1),size,path.artwork,path.reveal_width).save(output)
    return output


def _paper_indent(trace:tuple[tuple[Point,float],...],
                  size:tuple[int,int])->Image.Image:
    layer=Image.new("RGBA",size,(0,0,0,0))
    painter=ImageDraw.Draw(layer)
    for (a,pa),(b,pb) in zip(trace,trace[1:]):
        pressure=(pa+pb)*.5
        if pressure < .60:
            continue
        strength=round((pressure-.60)*80)
        painter.line(((a[0]+1,a[1]+1),(b[0]+1,b[1]+1)),
                     fill=(110,111,118,strength),width=6)
        painter.line(((a[0]-1,a[1]-1),(b[0]-1,b[1]-1)),
                     fill=(255,255,255,strength),width=2)
    return layer


def render_frames(path:PenPath,frames_dir:Path,
                  size:tuple[int,int]=(720,720),
                  timeline:MotionTimeline|None=None)->int:
    """60 FPS: speed changes in corners; nib remains attached until completed."""
    _validate_bounds(path,size)
    motion=timeline or MotionTimeline(path)
    frames_dir.mkdir(parents=True,exist_ok=True)
    for index in range(motion.frame_count):
        seconds=index/FRAME_RATE
        state=motion.at(seconds)
        trace=path.trace(state.progress)
        paper=Image.new("RGBA",size,"white")
        paper.alpha_composite(_paper_indent(trace,size))
        paper.alpha_composite(_ink_layer(trace,size,path.artwork,path.reveal_width))
        if seconds < motion.writing_seconds+.31:
            lift=max(0.,min(1.,(seconds-motion.writing_seconds)/.30))
            draw_ballpoint(paper,state.position,state.direction,lift)
        paper.convert("RGB").save(frames_dir/f"frame_{index:03d}.png")
    return motion.frame_count
