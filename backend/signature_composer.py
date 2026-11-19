"""General-purpose personal signature compositor for Hebrew and Latin names.

Layout is measured in unrestricted ink space, *then* fitted to the paper.
Letters and words have their own writing directions, while the name's primary
script controls global direction. This supports arbitrary name lengths and
mixed-script surnames without clipping or using one hard-coded example.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import ceil, cos, hypot, pi, sin
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from backend.font_signature import get_font, thin
from backend.name_rules import PreparedName, NameRun, prepare_name
from backend.pen_path import PenPath
from backend.stroke_route import route_skeleton
from backend.style_mapping import WritingStyle

Point = tuple[float, float]


@dataclass
class Glyph:
    image: Image.Image
    route: list[Point]
    top: float
    advance: float
    script: str


def _make_glyph(
    char: str, script: str, font, style: WritingStyle,
    variance: float,
) -> Glyph:
    """Keep the actual letter silhouette while personalizing geometry."""
    bbox = font.getbbox(char, anchor="ls")
    if bbox is None:
        raise ValueError(f"Handwriting font does not contain '{char}'")
    left, top, right, bottom = bbox
    image = Image.new("L", (max(8, right-left+12), max(8,bottom-top+12)), 0)
    ImageDraw.Draw(image).text(
        (6-left, 6-top), char, font=font, fill=255, anchor="ls"
    )
    ink_bbox = image.getbbox()
    if ink_bbox is None:
        raise ValueError(f"Handwriting letter has no ink: {char}")
    image = image.crop(ink_bbox)
    baseline_top = top + ink_bbox[1] - 6
    gx = style.width * (1 + variance * style.irregularity * .14)
    gy = style.height * (1 + variance * style.irregularity * .09)
    image = image.resize(
        (max(3, round(image.width*gx)), max(3, round(image.height*gy))),
        Image.Resampling.LANCZOS,
    )
    baseline_top *= gy
    if style.roundness > .76:
        image = image.filter(ImageFilter.GaussianBlur(.2 + .65*(style.roundness-.76)))
    if abs(style.slant) > .015:
        shear = style.slant * (.58 if script == "en" else .42)
        extra = ceil(abs(shear)*image.height)+4
        image = image.transform(
            (image.width+extra, image.height), Image.Transform.AFFINE,
            (1, -shear, shear*image.height/2-extra/2, 0, 1, 0),
            resample=Image.Resampling.BICUBIC,
        )
    if style.pressure > .80:
        image = image.filter(ImageFilter.MaxFilter(3))
    elif style.pressure < .24:
        # Keep hairlines visible; never erode an entire handwritten letter.
        pass
    pixels = image.load()
    foreground = {
        (x,y) for y in range(image.height) for x in range(image.width)
        if pixels[x,y] > 120
    }
    skeleton = thin(foreground)
    if len(skeleton) < 2:
        raise ValueError(f"Could not extract handwriting trajectory for '{char}'")
    nodes = route_skeleton(skeleton, rtl=script=="he")
    bridge = Image.new("L", image.size, 0)
    bridge_draw = ImageDraw.Draw(bridge)
    trajectory: list[Point] = [(float(nodes[0][0]), float(nodes[0][1]))]
    for a,b in zip(nodes,nodes[1:]):
        distance = hypot(b[0]-a[0], b[1]-a[1])
        if distance > 2.5:
            bridge_draw.line((a,b), fill=135, width=2)
        steps = max(1, ceil(distance / 1.8))
        for i in range(1,steps+1):
            fraction = i/steps
            trajectory.append((
                a[0] + (b[0]-a[0])*fraction,
                a[1] + (b[1]-a[1])*fraction,
            ))
    image = ImageChops.lighter(image, bridge)
    # Overlapping glyph widths generate a consistent cursive rhythm.
    tracking = .86 + .14*style.spacing if script=="he" else .81 + .14*style.spacing
    advance = max(4., image.width*tracking)
    return Glyph(image, trajectory, baseline_top, advance, script)


def _connector(a: Point, b: Point, previous: Point | None,
               following: Point | None, smoothness: float) -> list[Point]:
    """A tangent-aware pen-down join instead of a straight artificial bridge."""
    vx,vy = b[0]-a[0],b[1]-a[1]
    span = hypot(vx,vy)
    if span < .01:
        return [b]
    in_v = (a[0]-previous[0],a[1]-previous[1]) if previous else (vx,vy)
    out_v = (following[0]-b[0],following[1]-b[1]) if following else (vx,vy)
    in_n = max(.001,hypot(*in_v))
    out_n = max(.001,hypot(*out_v))
    reach = min(span*.27,25.*(.7+.3*smoothness))
    c1 = (a[0] + in_v[0]/in_n*reach, a[1]+in_v[1]/in_n*reach)
    c2 = (b[0] - out_v[0]/out_n*reach, b[1]-out_v[1]/out_n*reach)
    steps = max(10,min(56,round(span/1.3)))
    result = []
    for i in range(1,steps+1):
        t=i/steps
        u=1-t
        result.append((
            u*u*u*a[0]+3*u*u*t*c1[0]+3*u*t*t*c2[0]+t*t*t*b[0],
            u*u*u*a[1]+3*u*u*t*c1[1]+3*u*t*t*c2[1]+t*t*t*b[1],
        ))
    return result


def _flourish(
    end: Point, extent: tuple[float,float], style: WritingStyle,
    rtl: bool, font_size: int
) -> list[Point]:
    """One continuous and stylistically variable terminal signature gesture."""
    if style.flourish < .13:
        return []
    direction = -1 if rtl else 1
    low, high = extent
    reach = min(font_size*(.42 + 1.3*style.flourish), (high-low)*.30)
    reach = max(6.,reach)
    drop = font_size*(.05+.18*style.flourish)
    tail = [
        (end[0] + direction*reach*(t/40),
         end[1] - drop*sin(pi*t/40) - font_size*style.rise*.12*t/40)
        for t in range(1,41)
    ]
    if style.flourish < .58:
        return tail
    point = tail[-1]
    underline_reach = min((high-low)*.62, font_size*(1.0 + 3.1*style.flourish))
    # The final flourish doubles back below the name, like a real signature.
    base_y = point[1] + font_size*(.10+.19*style.flourish)
    tail.extend([
        (point[0]-direction*underline_reach*t/70,
         point[1] + (base_y-point[1])*sin(t/70*pi*.5))
        for t in range(1,71)
    ])
    if style.flourish > .86:
        point = tail[-1]
        tail.extend([
            (point[0]+direction*font_size*.14*sin(i/30*pi),
             point[1]-font_size*.21*sin(i/30*2*pi))
            for i in range(1,31)
        ])
    return tail


def _shapes_for_run(
    run: NameRun, font, style: WritingStyle, seeds: bytes,
    letter_index: int
) -> tuple[list[Glyph], float]:
    glyphs: list[Glyph] = []
    for char in run.text:
        variance = seeds[letter_index%len(seeds)]/255-.5
        glyphs.append(_make_glyph(char,run.script,font,style,variance))
        letter_index += 1
    width = sum(g.advance for g in glyphs[:-1]) + glyphs[-1].image.width
    return glyphs, width


def create_personal_signature(
    full_name: str, style: WritingStyle | None = None,
    portrait: bytes = b"", size: tuple[int,int]=(720,720),
    *, font_path: str | None = None,
) -> PenPath:
    """Generate one uninterrupted readable signature for any supported name."""
    prepared = prepare_name(full_name)
    if min(size) < 160:
        raise ValueError("Signature canvas is too small")
    style = style or WritingStyle()
    digest = sha256(prepared.display.encode("utf-8")+b"\x00"+portrait).digest()
    font_size = 104
    # Load only scripts actually present in this person's name.
    scripts = {run.script for run in prepared.runs}
    fonts = {
        script: get_font(
            font_size, font_path if script == "he" else None,
            script=script, weight=390 + style.pressure*230,
        )
        for script in scripts
    }
    runs: list[tuple[NameRun,list[Glyph],float,float]] = []
    cursor = 0.
    index = 0
    for run in prepared.runs:
        if runs:
            if run.gap_before:
                cursor += font_size*.34*style.spacing
            else:
                cursor += font_size*.08*style.spacing
        glyphs, width = _shapes_for_run(run,fonts[run.script],style,digest,index)
        runs.append((run,glyphs,cursor,width))
        cursor += width
        index += len(run.text)
    total_width = cursor
    rtl = prepared.primary_script=="he"
    elements: list[tuple[Image.Image,float,float]] = []
    path: list[Point] = []
    pressures: list[float] = []
    connectors: list[tuple[list[Point],float]] = []
    letter_index = 0
    for run,glyphs,run_start,run_width in runs:
        left = total_width - run_start - run_width if rtl else run_start
        offset = 0.
        for glyph in glyphs:
            x = (left + run_width - glyph.image.width - offset
                 if run.script=="he" else left+offset)
            drift = (digest[letter_index%32]/255-.5)*style.irregularity*7.
            y = (glyph.top + 125. + drift
                 -font_size*style.rise*letter_index/max(1,prepared.letter_count-1)*.35)
            elements.append((glyph.image,x,y))
            trace = [(px+x,py+y) for px,py in glyph.route]
            if path:
                transition=_connector(path[-1],trace[0],
                                      path[-2] if len(path)>1 else None,
                                      trace[1] if len(trace)>1 else None,
                                      style.roundness)
                connectors.append(([path[-1]]+transition,
                                   style.pressure))
                path.extend(transition)
                pressures.extend([max(.1,style.pressure*.85)]*len(transition))
            for i,p in enumerate(trace):
                path.append(p)
                variation = .075*sin(i*.13+letter_index*1.31)
                pressures.append(max(.1,min(1.,style.pressure*(1+variation))))
            offset += glyph.advance
            letter_index += 1
    flourished=_flourish(path[-1],(0.,total_width),style,rtl,font_size)
    if flourished:
        connectors.append(([path[-1]]+flourished,style.pressure))
        path.extend(flourished)
        pressures.extend([
            max(.1,style.pressure*(.92-.26*(i+1)/len(flourished)))
            for i in range(len(flourished))
        ])
    x0=min([p[0] for p in path]+[x for _,x,_ in elements])
    x1=max([p[0] for p in path]+[x+img.width for img,x,_ in elements])
    y0=min([p[1] for p in path]+[y for _,_,y in elements])
    y1=max([p[1] for p in path]+[y+img.height for img,_,y in elements])
    padding=12
    raw_width=max(2,ceil(x1-x0)+padding*2)
    raw_height=max(2,ceil(y1-y0)+padding*2)
    canvas=Image.new("L",(raw_width,raw_height),0)
    for img,x,y in elements:
        left_px=round(x-x0+padding)
        top_px=round(y-y0+padding)
        crop=canvas.crop((left_px,top_px,left_px+img.width,top_px+img.height))
        canvas.paste(ImageChops.lighter(crop,img),(left_px,top_px))
    draw=ImageDraw.Draw(canvas)
    for connector,_ in connectors:
        draw.line([(x-x0+padding,y-y0+padding) for x,y in connector],
                  fill=round(168+65*style.pressure),
                  width=max(2,round(font_size*.028*(.7+.5*style.pressure))),
                  joint="curve")
    # Enforce fit after all glyphs and the flourish are known; no hard-coded
    # cursor positions or changes in letter order for long surnames.
    scale = min((size[0]-110)/raw_width, (size[1]-240)/raw_height, 1.65)
    scaled_w = max(1,round(raw_width*scale))
    scaled_h = max(1,round(raw_height*scale))
    off_x=round((size[0]-scaled_w)/2)
    off_y=round((size[1]-scaled_h)/2)
    result=Image.new("L",size,0)
    result.paste(canvas.resize((scaled_w,scaled_h),Image.Resampling.LANCZOS),
                 (off_x,off_y))
    fitted = tuple((
        off_x+(x-x0+padding)*scaled_w/raw_width,
        off_y+(y-y0+padding)*scaled_h/raw_height,
    ) for x,y in path)
    if not all(0 <= x < size[0] and 0 <= y < size[1] for x,y in fitted):
        raise ValueError("Unable to fit signature to canvas")
    nib = max(3,min(20,round(font_size*.086*scale)))
    # No detached font pixels may materialize suddenly at the end of video:
    # restrict export artwork to the exact area physically swept by the nib.
    brush=Image.new("L",size,0)
    painter=ImageDraw.Draw(brush)
    painter.line(fitted,fill=255,width=nib,joint="curve")
    result=ImageChops.multiply(result,brush)
    return PenPath(fitted,tuple(pressures),style.speed,
                   artwork=result,reveal_width=nib)
