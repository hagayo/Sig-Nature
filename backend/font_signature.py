"""Handwriting-based Hebrew signature, derived from Gveret Levin glyphs.

The open handwriting font supplies recognisable Hebrew letterforms. The pen
route, joins and final flourishes are generated as ONE visible continuous ink
trajectory, never an unrelated overlaid animation.
"""
from hashlib import sha256
from math import sin, pi, ceil, hypot
from pathlib import Path
import os
from urllib.request import urlopen

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from backend.stroke_route import route_skeleton

HEBREW = set('אבגדהוזחטיכלמנסעפצקרשתךםןףץ')
FONT_URL = ('https://raw.githubusercontent.com/AlefAlefAlef/gveret-levin/'
            'master/fonts/ttf/GveretLevin-Regular.ttf')


def get_font(
    size: int,
    font_path: str | None = None,
    script: str = "he",
    weight: float = 450,
) -> ImageFont.FreeTypeFont:
    """Load bundled open handwriting fonts without network dependencies.

    A caller-supplied font override remains available for debugging, and the
    Hebrew default preserves the original get_font(size) API.
    """
    if script not in {"he", "en"}:
        raise ValueError("Unsupported handwriting script")
    if not 8 <= size <= 220:
        raise ValueError("Invalid handwriting font size")
    default = (
        Path(__file__).resolve().parent / "assets" /
        ("GveretLevin-Regular.ttf" if script == "he" else "Caveat-Variable.ttf")
    )
    override = (
        font_path
        or os.environ.get("SIG_NATURE_HEBREW_FONT" if script == "he"
                          else "SIG_NATURE_LATIN_FONT")
    )
    font_file = Path(override) if override else default
    if not font_file.is_file():
        raise RuntimeError(
            f"Handwriting font for {script} is unavailable at {font_file}"
        )
    font = ImageFont.truetype(str(font_file), size)
    if script == "en" and hasattr(font, "get_variation_axes"):
        try:
            axes = font.get_variation_axes()
            values = [
                max(axis["minimum"], min(axis["maximum"], float(weight)))
                if "weight" in str(axis["name"]).lower()
                else axis["default"]
                for axis in axes
            ]
            if values:
                font.set_variation_by_axes(values)
        except (OSError, ValueError, KeyError, TypeError):
            pass
    return font

def thin(foreground: set[tuple[int,int]]) -> set[tuple[int,int]]:
    """Zhang-Suen thinning to extract a one-pixel pen trajectory guide."""
    mask = set(foreground)
    around = ((0,-1),(1,-1),(1,0),(1,1),(0,1),(-1,1),(-1,0),(-1,-1))
    for _ in range(100):
        removed = 0
        for phase in (0,1):
            discard = []
            for x,y in mask:
                n = [(x+dx,y+dy) in mask for dx,dy in around]
                if not 2 <= sum(n) <= 6: continue
                if sum(not n[i] and n[(i+1)%8] for i in range(8)) != 1: continue
                north,east,south,west = n[0],n[2],n[4],n[6]
                if phase == 0 and ((north and east and south) or (east and south and west)): continue
                if phase == 1 and ((north and east and west) or (north and south and west)): continue
                discard.append((x,y))
            mask.difference_update(discard)
            removed += len(discard)
        if not removed: break
    return mask


def create_hebrew_signature(name: str, style, portrait: bytes = b'',
                            size: tuple[int,int] = (720,720),
                            font_path: str | None = None):
    """Return PenPath with real font artwork and an uninterrupted writing route."""
    from backend.pen_path import PenPath
    clean=' '.join(name.split())
    if not clean or any(c!=' ' and c not in HEBREW for c in clean):
        raise ValueError('Expected a Hebrew name')
    if len(clean.replace(' ',''))>32 or min(size)<160:
        raise ValueError('Name is too long or canvas too small')
    font_size=min(115,round((size[0]-130)/max(5,len(clean)*.68)))
    font=get_font(font_size,font_path)
    # Fit long names even when the portrait produces wide, spaced letters.
    for _ in range(5):
        advance=sum((font.getlength(c)*style.spacing*max(1,style.width)
                     if c != ' ' else font_size*.37*style.spacing)
                    for c in clean)
        if advance <= size[0]-155: break
        font_size=max(10,int(font_size*(size[0]-165)/advance))
        font=get_font(font_size,font_path)
    glyphs=Image.new('L',size,0)
    cursor=float(size[0]-65)
    baseline=size[1]*.5+36
    count=len(clean.replace(' ',''))
    all_points=[];pressures=[]
    digest=sha256(clean.encode('utf-8')+b'\x00'+portrait).digest()
    index=0
    for char in clean:
        if char==' ':
            cursor-=font_size*.37*style.spacing
            continue
        box=font.getbbox(char,anchor='ls')
        width,height=box[2]-box[0],box[3]-box[1]
        image=Image.new('L',(max(1,width+6),max(1,height+6)),0)
        ImageDraw.Draw(image).text((3-box[0],3-box[1]),char,font=font,anchor='ls',fill=255)
        irregular=(digest[index%32]/255-.5)*style.irregularity*.11
        new_w=max(3,round(image.width*style.width*(1+irregular)))
        new_h=max(3,round(image.height*style.height))
        image=image.resize((new_w,new_h),Image.Resampling.LANCZOS)
        if style.roundness > .65:
            image=image.filter(ImageFilter.GaussianBlur(.5+(style.roundness-.65)*1.2))
        if abs(style.slant) > .01:
            shear=style.slant*.45
            padding=ceil(abs(shear)*image.height)+4
            image=image.transform(
                (image.width+padding,image.height),Image.Transform.AFFINE,
                (1,-shear,shear*image.height/2-padding/2,0,1,0),
                resample=Image.Resampling.BICUBIC)
        # Pressure influences physical stroke thickness across the entire
        # range, without eroding delicate handwritten letterforms.
        if style.pressure > .88:
            image = image.filter(ImageFilter.MaxFilter(5))
        elif style.pressure > .60:
            image = image.filter(ImageFilter.MaxFilter(3))
        # Low pressure stays thin rather than deleting essential letter ink.
        left=round(cursor-image.width+style.slant*font_size*.13)
        top=round(baseline+box[1]*style.height-3*style.height
                  -style.rise*index/max(1,count-1)*font_size*.4
                  +irregular*font_size)
        if left<0 or top<0 or left+image.width>=size[0] or top+image.height>=size[1]:
            raise ValueError('Name does not fit canvas')
        pixels=image.load()
        filled={(x,y) for y in range(image.height) for x in range(image.width)
                if pixels[x,y]>120}
        if not filled:raise ValueError('Missing letter geometry')
        skeleton=thin(filled)
        original_route=route_skeleton(skeleton)
        route=[original_route[0]]
        bridge=Image.new('L',image.size,0)
        nib=ImageDraw.Draw(bridge)
        for a,b in zip(original_route,original_route[1:]):
            distance=hypot(b[0]-a[0],b[1]-a[1])
            if distance>2.5:
                # Disconnected font components need a real, faint ink bridge.
                nib.line([a,b],fill=115,width=2)
            steps=max(1,ceil(distance/2))
            for j in range(1,steps+1):
                t=j/steps
                route.append((a[0]*(1-t)+b[0]*t,a[1]*(1-t)+b[1]*t))
        image=ImageChops.lighter(image,bridge)
        part=Image.new('L',size,0);part.paste(image,(left,top))
        glyphs=ImageChops.lighter(glyphs,part)
        points=[(x+left,y+top) for x,y in route]
        if all_points:
            a,b=all_points[-1],points[0]
            # Cubic tangent connector in the same ink weight and writing flow.
            # The first and last velocities follow the actual ink stroke.
            px,py = all_points[-2] if len(all_points)>1 else (a[0]+5,a[1])
            if len(points)>1:
                qx,qy=points[1]
            else:
                qx,qy=b[0]-5,b[1]
            dx=b[0]-a[0]
            span=max(3,abs(dx))
            curve=max(.10,min(.96,style.roundness))
            c1=(a[0]-span*(.21+.18*curve),
                a[1]+(a[1]-py)*.24+font_size*(curve-.5)*.025)
            c2=(b[0]+span*(.20+.18*curve),
                b[1]-(qy-b[1])*.24+font_size*(curve-.5)*.04)
            join=[]
            for j in range(1,25):
                t=j/24
                u=1-t
                join.append((u**3*a[0]+3*u*u*t*c1[0]+3*u*t*t*c2[0]+t**3*b[0],
                             u**3*a[1]+3*u*u*t*c1[1]+3*u*t*t*c2[1]+t**3*b[1]))
            connector=Image.new('L',size,0)
            ImageDraw.Draw(connector).line([a]+join,fill=220,width=max(2,round(font_size*.034)),joint='curve')
            glyphs=ImageChops.lighter(glyphs,connector)
            all_points.extend(join)
            pressures.extend([style.pressure*.87]*len(join))
        all_points.extend(points)
        # Slight, repeatable pen-pressure modulation across each letter.
        # This creates ink texture rather than identical geometric strokes.
        for point_index in range(len(points)):
            variation = .075*sin(point_index*.125 + index*1.7)
            variation += .035*sin(point_index*.049 + index*.9)
            pressures.append(max(.10, min(1., style.pressure*(1+variation))))
        cursor-=font.getlength(char)*style.spacing*style.width
        index+=1
    if style.flourish > .12:
        # Finish with a gesture drawn in the same direction as handwriting:
        # first stretch the last letter; energetic handwriting can curve back
        # into a continuous underline/loop. This NEVER lifts the nib.
        start=all_points[-1]
        reach=min(max(0,start[0]-16),font_size*(.20+1.10*style.flourish))
        if reach>4:
            tail=[]
            for j in range(1,49):
                t=j/48
                tail.append((start[0]-reach*t,
                             start[1]+font_size*.18*style.flourish*sin(pi*t)
                             -font_size*.10*style.rise*t))
            all_points.extend(tail)
            pressures.extend([style.pressure*(.90-.22*(j+1)/48) for j in range(48)])
            connector=Image.new('L',size,0)
            artist=ImageDraw.Draw(connector)
            artist.line([start]+tail,fill=232,width=max(2,round(font_size*.038)),joint='curve')
            if style.flourish > .60:
                end=tail[-1]
                text_right=max(p[0] for p in all_points)
                length=min((text_right-end[0])*.75,
                           font_size*(1.3+3.1*style.flourish))
                base_y=max(p[1] for p in all_points)+font_size*.14
                c1=(end[0]-font_size*.19,end[1]+font_size*.19)
                c2=(end[0]+length*.25,base_y+font_size*.14)
                underline=[]
                for j in range(1,65):
                    t=j/64
                    u=1-t
                    p=(u**3*end[0]+3*u*u*t*c1[0]+3*u*t*t*c2[0]+t**3*(end[0]+length),
                       u**3*end[1]+3*u*u*t*c1[1]+3*u*t*t*c2[1]+t**3*base_y)
                    underline.append(p)
                # On expressive signatures, loop back elegantly at the end.
                if style.flourish>.85:
                    e=underline[-1]
                    underline.extend((
                        (e[0]+font_size*.16*sin(pi*j/32),
                         e[1]-font_size*.22*sin(2*pi*j/32))
                        for j in range(1,33)
                    ))
                all_points.extend(underline)
                pressures.extend([style.pressure*.65]*len(underline))
                artist.line([end]+underline,fill=225,
                            width=max(2,round(font_size*.034)),joint='curve')
            glyphs=ImageChops.lighter(glyphs,connector)
    # Preserve image bounds for tall ascenders and the optional underline.
    if any(x<1 or y<1 or x>=size[0]-1 or y>=size[1]-1 for x,y in all_points):
        raise ValueError('Signature flourishes do not fit the canvas')
    # The final artwork is restricted to the *actual swept pen area*.
    # Without this, pixels not traversed by the nib would pop into view on
    # the last animation frame, violating the single-contact contract.
    nib_width = max(6, min(16, round(font_size * .095)))
    swept = Image.new("L", size, 0)
    brush = ImageDraw.Draw(swept)
    brush.line(all_points, fill=255, width=nib_width, joint="curve")
    radius = nib_width / 2
    sx, sy = all_points[0]
    brush.ellipse((sx-radius, sy-radius, sx+radius, sy+radius), fill=255)
    glyphs = ImageChops.multiply(glyphs, swept)
    # Make higher pressure visibly darker in both exported PNG and MP4.
    # This layer is derived entirely from the same continuous pen trajectory.
    pigment = Image.new("L", size, 0)
    pig_draw = ImageDraw.Draw(pigment)
    for i in range(1, len(all_points)):
        amount = (pressures[i-1] + pressures[i]) / 2
        darkness = round(180 + 75 * amount)
        pig_draw.line((all_points[i-1], all_points[i]),
                      fill=darkness, width=nib_width+2)
    glyphs = ImageChops.multiply(glyphs, pigment)
    return PenPath(tuple(all_points), tuple(pressures), style.speed,
                   artwork=glyphs, reveal_width=nib_width)
