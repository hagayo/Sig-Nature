"""Anti-aliased nib-anchored ballpoint pen for realistic signature animation.

Generated shaded pen artwork is cached per wrist angle and rendered at 2x.
The nib is always placed at the current pen-down path endpoint.
"""
from functools import lru_cache
from math import hypot

from PIL import Image, ImageDraw, ImageFilter

SPRITE_SIZE = (240, 280)
ANCHOR = (58, 246)
SCALE = 2


def _points(axis, positions):
    u, v = axis
    return [((ANCHOR[0] + u[0] * s + v[0] * side) * SCALE,
             (ANCHOR[1] + u[1] * s + v[1] * side) * SCALE)
            for s, side in positions]


@lru_cache(maxsize=41)
def _sprite(bucket: int) -> Image.Image:
    tilt = max(-20, min(20, bucket)) * .012
    ux, uy = .35 + tilt, -.94 + tilt * .38
    unit = hypot(ux, uy)
    u = (ux / unit, uy / unit)
    v = (-u[1], u[0])
    axis = (u, v)
    size = tuple(n * SCALE for n in SPRITE_SIZE)
    shadow = Image.new('RGBA', size)
    sd = ImageDraw.Draw(shadow)
    silhouette = _points(axis, [(7,-3),(34,-7),(77,-11),(185,-11),
                                (195,-7),(195,7),(185,11),(77,11),(34,7),(7,3)])
    sd.polygon([(x+7,y+9) for x,y in silhouette], fill=(10,18,38,78))
    shadow = shadow.filter(ImageFilter.GaussianBlur(4.0 * SCALE))
    overlay = Image.new('RGBA', size)
    d = ImageDraw.Draw(overlay)

    def shape(vertices, color):
        d.polygon(_points(axis, vertices), fill=color)

    def line(vertices, color, width=1):
        d.line(_points(axis, vertices), fill=color,
               width=max(1,int(width*SCALE)), joint='curve')

    shape([(73,-12),(186,-11),(195,-8),(195,8),(186,11),(73,12)], '#182f68')
    shape([(76,-7),(188,-7),(193,-4),(193,6),(77,7)], '#2d5ba5')
    shape([(79,-4),(189,-5),(191,-2),(191,2),(79,3)], '#4981cf')
    line([(84,-3),(181,-4)], (173,210,255,195), 2)
    line([(91,9),(185,8)], (9,28,69,150), 1.3)
    shape([(33,-8),(72,-12),(79,-11),(79,11),(72,12),(33,8)], '#14264c')
    shape([(36,-5),(72,-8),(77,-7),(77,5),(36,5)], '#274474')
    for s in range(40,76,6):
        line([(s,-8.1),(s,8)], (13,24,46,185), 1)
    shape([(0,-.7),(7,-2.5),(21,-4.5),(34,-8),(36,8),
           (21,4.5),(7,2.5),(0,.7)], '#87919f')
    shape([(2,-.4),(10,-1.2),(31,-5.6),(32,-1.5),(11,1.2)], '#e2e8ee')
    line([(6,-.1),(28,-2.2)], (255,255,255,195), .9)
    line([(7,2.2),(31,5.4)], '#4d596c', .8)
    line([(33,-8.5),(33,8.5)], '#d2d7dd', 2.6)
    line([(78,-11.3),(78,11.3)], '#aab9d0', 2.1)
    line([(79,-9),(79,9)], (242,248,255,190), .8)
    line([(184,12),(155,15),(116,16)], '#a5b5c8', 2.8)
    line([(178,12.5),(151,13.2),(116,14)], '#ebf3fb', .95)
    d.ellipse([((ANCHOR[0]-.85)*SCALE,(ANCHOR[1]-.85)*SCALE),
               ((ANCHOR[0]+.85)*SCALE,(ANCHOR[1]+.85)*SCALE)],
              fill='#273347')
    image = Image.alpha_composite(shadow,overlay)
    return image.resize(SPRITE_SIZE,Image.Resampling.LANCZOS)


def draw_ballpoint(
    canvas: Image.Image,
    tip: tuple[float,float],
    direction: tuple[float,float],
    lift: float=0.,
) -> None:
    """Composites tip-locked shading and lifts only after finishing the ink."""
    bucket = round(max(-20.,min(20.,direction[1]*12+direction[0]*5)))
    sprite = _sprite(bucket)
    x = round(tip[0]-ANCHOR[0]+lift*13)
    y = round(tip[1]-ANCHOR[1]-lift*30)
    if lift > .80:
        sprite = sprite.copy()
        sprite.putalpha(sprite.getchannel('A').point(
            lambda a: round(a*max(0.,(1.-lift)/.2))))
    canvas.alpha_composite(sprite,(x,y))
