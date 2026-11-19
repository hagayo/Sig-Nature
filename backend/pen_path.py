"""The only source of truth for signature ink is a single pen-down path."""
from dataclasses import dataclass, field
from math import hypot, isfinite
from pathlib import Path

from PIL import Image, ImageDraw, ImageChops

from backend.animation import FRAME_COUNT

Point = tuple[float, float]
INK = (25, 42, 115)


@dataclass(frozen=True)
class PenPath:
    """Pen positions and pressure samples; no lift/teleport operation exists."""

    points: tuple[Point, ...]
    pressures: tuple[float, ...] = ()
    tempo: float = 0.5
    artwork: Image.Image | None = field(default=None, compare=False, repr=False)

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("Pen path needs at least two points")
        if any(not all(isfinite(v) for v in p) for p in self.points):
            raise ValueError("Pen path contains non-finite coordinates")
        if self.pressures and len(self.pressures) != len(self.points):
            raise ValueError("A pressure value is required for every pen point")
        if any(not isfinite(v) or not 0 <= v <= 1 for v in self.pressures):
            raise ValueError("Invalid pen pressure")
        if not isfinite(self.tempo) or not 0 <= self.tempo <= 1:
            raise ValueError("Invalid writing tempo")
        if self.length <= 0:
            raise ValueError("Pen path has zero length")

    @property
    def length(self) -> float:
        return sum(hypot(b[0]-a[0],b[1]-a[1])
                   for a,b in zip(self.points,self.points[1:]))

    def trace(self, fraction: float) -> tuple[tuple[Point,float],...]:
        """Exact travelled-distance prefix, with interpolated pressure at the tip."""
        if not isfinite(fraction) or not 0 <= fraction <= 1:
            raise ValueError("Progress must be finite and between 0 and 1")
        pressure = self.pressures or (1.0,)*len(self.points)
        if fraction == 1:
            return tuple(zip(self.points, pressure))
        if fraction == 0:
            return ((self.points[0], pressure[0]),)
        remaining=self.length*fraction
        result=[(self.points[0],pressure[0])]
        for i,(a,b) in enumerate(zip(self.points,self.points[1:])):
            d=hypot(b[0]-a[0],b[1]-a[1])
            if d == 0:
                continue
            if remaining >= d:
                result.append((b,pressure[i+1]))
                remaining-=d
            else:
                alpha=remaining/d
                result.append(((a[0]+(b[0]-a[0])*alpha,
                                a[1]+(b[1]-a[1])*alpha),
                               pressure[i]+(pressure[i+1]-pressure[i])*alpha))
                break
        return tuple(result)

    def prefix(self,fraction:float)->tuple[Point,...]:
        return tuple(p for p,_ in self.trace(fraction))


def _validate_bounds(path:PenPath,size:tuple[int,int])->None:
    if path.artwork is not None and path.artwork.size != size:
        raise ValueError("Artwork size does not match output canvas")
    if min(size) <= 0:
        raise ValueError("Canvas dimensions must be positive")
    if any(not (0 <= x < size[0] and 0 <= y < size[1])
           for x,y in path.points):
        raise ValueError("Pen path contains a point outside the canvas")


def _ink_layer(trace:tuple[tuple[Point,float],...],
               size:tuple[int,int], artwork:Image.Image | None = None)->Image.Image:
    """Reveal only font ink touched by the continuous pen path, if supplied."""
    if artwork is not None:
        swept=Image.new("L",size,0)
        writer=ImageDraw.Draw(swept)
        if len(trace)>1:
            writer.line([point for point,_ in trace],fill=255,width=19,
                        joint="curve")
        else:
            x,y=trace[0][0]
            writer.ellipse((x-9,y-9,x+9,y+9),fill=255)
        alpha=ImageChops.multiply(artwork,swept)
        result=Image.new("RGBA",size,(*INK,0))
        result.putalpha(alpha)
        return result
    # Legacy line-only rendering remains for Latin glyphs and small test paths.
    layer=Image.new("RGBA",size,(0,0,0,0))
    draw=ImageDraw.Draw(layer)
    for (a,pa),(b,pb) in zip(trace,trace[1:]):
        pressure=(pa+pb)*.5
        width=max(1,round(1.35+pressure*4.7))
        alpha=min(255,round(165+pressure*90))
        ink=(*INK,alpha)
        draw.line((a,b),fill=ink,width=width)
        radius=width/2
        draw.ellipse((b[0]-radius,b[1]-radius,
                      b[0]+radius,b[1]+radius),fill=ink)
    if len(trace)==1:
        a,p=trace[0]
        draw.ellipse((a[0]-1,a[1]-1,a[0]+1,a[1]+1),fill=(*INK,255))
    return layer


def render_signature(
    path:PenPath,output:Path,size:tuple[int,int]=(720,720)
)->Path:
    """Transparent PNG exactly matching the final animated ink."""
    _validate_bounds(path,size)
    output.parent.mkdir(parents=True,exist_ok=True)
    _ink_layer(path.trace(1),size,path.artwork).save(output)
    return output



def _paper_indent(trace: tuple[tuple[Point,float],...], size:tuple[int,int])->Image.Image:
    """Subtle paper highlight and depression shadow at stronger pen pressure."""
    layer=Image.new("RGBA",size,(0,0,0,0))
    painter=ImageDraw.Draw(layer)
    for (a,pa),(b,pb) in zip(trace,trace[1:]):
        pressure=(pa+pb)*.5
        if pressure < .60:
            continue
        strength=round((pressure-.60)*110)
        painter.line(((a[0]+1,a[1]+1),(b[0]+1,b[1]+1)),
                     fill=(110,111,118,strength),width=7)
        painter.line(((a[0]-1,a[1]-1),(b[0]-1,b[1]-1)),
                     fill=(255,255,255,strength),width=2)
    return layer


def render_frames(
    path:PenPath,frames_dir:Path,size:tuple[int,int]=(720,720)
)->None:
    """36 successive path prefixes on paper, with a pen tip on the live endpoint."""
    _validate_bounds(path,size)
    frames_dir.mkdir(parents=True,exist_ok=True)
    for index in range(FRAME_COUNT):
        elapsed=(index+1)/FRAME_COUNT
        trace=path.trace(elapsed ** (1.3 - .6*path.tempo))
        paper=Image.new("RGBA",size,"white")
        paper.alpha_composite(_paper_indent(trace,size))
        paper.alpha_composite(_ink_layer(trace,size,path.artwork))
        tip,_=trace[-1]
        x,y=tip
        pen=ImageDraw.Draw(paper)
        # Blue ballpoint's nib touches the *actual* last written point.
        pen.line(((x+37,y-84),(x+10,y-21)),fill=(42,66,135,255),width=13)
        pen.line(((x+14,y-27),(x,y)),fill=(170,174,181,255),width=5)
        pen.line(((x+37,y-84),(x+18,y-40)),fill=(100,130,194,255),width=3)
        paper.convert("RGB").save(frames_dir/f"frame_{index:03d}.png")
