"""Noto Sans Hebrew letter geometry routed as one continuous pen-down stroke.

Based on the real font silhouettes, not hand-invented symbol sketches.
Noto Sans Hebrew is OFL-1.1; no font binaries are stored in this repository.
"""
from collections import deque
from hashlib import sha256
from math import sin, pi, ceil, hypot
from pathlib import Path
import os
from urllib.request import urlopen

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

HEBREW = set('אבגדהוזחטיכלמנסעפצקרשתךםןףץ')
NEIGHBORS = ((1,0),(-1,0),(0,1),(0,-1),(1,1),(-1,1),(-1,-1),(1,-1))
FONT_URL = ('https://raw.githubusercontent.com/google/fonts/main/ofl/'
            'notosanshebrew/NotoSansHebrew%5Bwdth%2Cwght%5D.ttf')


def get_font(size: int, font_path: str | None = None) -> ImageFont.FreeTypeFont:
    paths = [font_path, os.environ.get('SIG_NATURE_HEBREW_FONT'),
             '/usr/share/fonts/truetype/noto/NotoSansHebrew-Light.ttf',
             '/usr/share/fonts/truetype/noto/NotoSansHebrew-Regular.ttf',
             'C:/Windows/Fonts/NotoSansHebrew-Regular.ttf']
    cached = Path.home()/'.cache'/'sig-nature'/'NotoSansHebrew-variable.ttf'
    paths.append(str(cached))
    font_file = next((p for p in paths if p and Path(p).is_file()), None)
    if font_file is None:
        cached.parent.mkdir(parents=True, exist_ok=True)
        try:
            with urlopen(FONT_URL, timeout=20) as response:
                data = response.read(1_000_001)
            if len(data)>1_000_000 or data[:4] != b'\x00\x01\x00\x00':
                raise ValueError('Downloaded Noto font was invalid')
            cached.write_bytes(data)
        except Exception as exc:
            raise RuntimeError('Noto Sans Hebrew unavailable; download it from Google Fonts or set SIG_NATURE_HEBREW_FONT') from exc
        font_file = str(cached)
    font = ImageFont.truetype(font_file, size)
    if 'variable' in font_file.lower():
        axes = font.get_variation_axes()
        values = [300 if b'weight' in a['name'].lower() else a['default'] for a in axes]
        font.set_variation_by_axes(values)
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


def pen_route(skeleton: set[tuple[int,int]]) -> list[tuple[int,int]]:
    """One DFS route through all glyph strokes, with short visible joins."""
    edges = {p: {(p[0]+dx,p[1]+dy) for dx,dy in NEIGHBORS
                 if (p[0]+dx,p[1]+dy) in skeleton} for p in skeleton}
    components = []
    seen = set()
    for p in sorted(skeleton):
        if p in seen: continue
        todo=[p]; seen.add(p); part=[]
        while todo:
            node=todo.pop(); part.append(node)
            for nxt in edges[node]:
                if nxt not in seen: seen.add(nxt); todo.append(nxt)
        components.append(part)
    while len(components)>1:
        dist,a,b,ia,ib = min(
            ((p[0]-q[0])**2+(p[1]-q[1])**2,p,q,i,j)
            for i,left in enumerate(components)
            for j,right in enumerate(components) if j>i
            for p in left for q in right
        )
        edges[a].add(b); edges[b].add(a)
        components[ia].extend(components[ib]); components.pop(ib)
    tips=[p for p,n in edges.items() if len(n)<=1]
    start=max(tips or list(skeleton),key=lambda p:(p[0],p[1]))
    goal=min(tips or list(skeleton),key=lambda p:(p[0],-p[1]))
    parents={start:None}; children={p:[] for p in skeleton}
    todo=deque([start])
    while todo:
        node=todo.popleft()
        for nxt in sorted(edges[node]):
            if nxt not in parents:
                parents[nxt]=node; children[node].append(nxt);todo.append(nxt)
    spine=set(); node=goal
    while node is not None: spine.add(node);node=parents[node]
    positions=[start]
    def walk(node):
        for nxt in children[node]:
            if nxt not in spine:
                positions.append(nxt);walk(nxt);positions.append(node)
        for nxt in children[node]:
            if nxt in spine:positions.append(nxt);walk(nxt)
    walk(start)
    return positions


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
        if style.pressure>.80:image=image.filter(ImageFilter.MaxFilter(3))
        if style.pressure<.27:image=image.filter(ImageFilter.MinFilter(3))
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
        original_route=pen_route(skeleton)
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
            join=[]
            for j in range(1,25):
                t=j/24
                join.append((a[0]+(b[0]-a[0])*t,
                             a[1]+(b[1]-a[1])*t+3*sin(t*pi)))
            connector=Image.new('L',size,0)
            ImageDraw.Draw(connector).line([a]+join,fill=130,width=2)
            glyphs=ImageChops.lighter(glyphs,connector)
            all_points.extend(join);pressures.extend([.18]*len(join))
        all_points.extend(points);pressures.extend([style.pressure]*len(points))
        cursor-=font.getlength(char)*style.spacing*style.width
        index+=1
    if style.flourish > .12:
        start=all_points[-1]
        reach=min(max(0,start[0]-22),font_size*(.14+.55*style.flourish))
        if reach>3:
            extension=[(start[0]-reach*(i/36),
                        start[1]+font_size*.12*style.flourish*sin(pi*i/36)
                        -font_size*.10*style.rise*i/36)
                       for i in range(1,37)]
            connector=Image.new('L',size,0)
            ImageDraw.Draw(connector).line([start]+extension,fill=130,width=2)
            glyphs=ImageChops.lighter(glyphs,connector)
            all_points.extend(extension);pressures.extend([.23]*len(extension))
    return PenPath(tuple(all_points),tuple(pressures),style.speed,artwork=glyphs)
