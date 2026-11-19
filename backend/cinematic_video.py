"""Photographic macro cinematography for Sig-Nature handwriting videos.

Photographic, optically isolated images of a real-looking ballpoint nib and a
textured paper sheet are composited on an oblique tracked paper plane. The ink
is revealed strictly by the original pen-down path. No top-down cartoon pen,
no prompt-per-frame image instability, no generative video or camera teleports.

The bundled two image textures come from an earlier user-generated macro-pen
illustration (not a stock website). The pen photo supplies its actual material
specular highlights, tip and transparent grip; no vector substitute is used.
"""
from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache
from math import ceil, cos, sin
from pathlib import Path
import subprocess
from typing import Iterator

import cv2
import numpy as np
from PIL import Image

from backend.motion import FRAME_RATE, MotionTimeline

ASSETS = Path(__file__).resolve().parent / "assets"
OUTPUT_SIZE = (1280, 720)
PAPER_SIZE = 1700
WORLD_SUPERSAMPLE = 2
PAPER_SHEAR = -.14
PAPER_FORESHORTEN = .60
MACRO_ZOOM = 2.65
REVEAL_SECONDS = 1.65


@lru_cache(maxsize=1)
def _assets() -> tuple[np.ndarray, np.ndarray]:
    """Load photographic, color-managed reference materials or fail explicitly."""
    pen_file, paper_file = ASSETS / "pen_macro.webp", ASSETS / "paper_macro.webp"
    if not pen_file.is_file() or not paper_file.is_file():
        raise FileNotFoundError("Photographic macro materials missing from backend/assets")
    pen_rgba = np.array(Image.open(pen_file).convert("RGBA"))
    paper_rgb = np.array(Image.open(paper_file).convert("RGB"))
    if pen_rgba.shape[2] != 4 or pen_rgba.shape[0] < 300:
        raise ValueError("Invalid photographic pen material")
    return pen_rgba, paper_rgb


def validate_cinematic_materials() -> None:
    """Check required photographic textures before spending OpenAI credits."""
    _assets()


@lru_cache(maxsize=1)
def _paper_world() -> np.ndarray:
    """Real photographed paper fibres, normalized to avoid tiled lighting bands."""
    _, paper = _assets()
    sample = paper.astype(np.float32)
    high_pass = sample - cv2.GaussianBlur(sample, (0, 0), 15)
    # Repeated *grain*, not repeated lighting patches or text.
    reflect = np.concatenate([high_pass, high_pass[::-1,:,:]], axis=0)
    reflect = np.concatenate([reflect, reflect[:,::-1,:]], axis=1)
    reps = (ceil(PAPER_SIZE / reflect.shape[0]), ceil(PAPER_SIZE / reflect.shape[1]), 1)
    grain = np.tile(reflect, reps)[:PAPER_SIZE,:PAPER_SIZE]
    seed = np.random.default_rng(3107)
    sensor = seed.normal(0, .75, size=(PAPER_SIZE,PAPER_SIZE,1)).astype(np.float32)
    yy, xx = np.mgrid[:PAPER_SIZE,:PAPER_SIZE]
    warm = 3.0 * (xx/PAPER_SIZE) + 2.0 * (yy/PAPER_SIZE)
    base = np.array([245.,242.5,240.], dtype=np.float32)
    paper = base + 1.55*grain + sensor - warm[:,:,None]
    return np.uint8(np.clip(paper, 0, 255))


@lru_cache(maxsize=1)
def _optical_layers():
    w,h=OUTPUT_SIZE
    yy,xx=np.mgrid[:h,:w].astype(np.float32)
    radius=((xx-w*.47)/(w*.74))**2+((yy-h*.49)/(h*.79))**2
    vignette=np.clip(1.-.085*radius,.90,1.02)
    # A broad side-lit window highlight, not a flat computer background.
    light=np.exp(-(((xx-w*.18)/(w*.50))**2 + ((yy-h*.12)/(h*.70))**2))
    illumination=np.clip(vignette+light*.035,.86,1.10).astype(np.float32)
    return xx,yy,illumination


def _photo_sprite(scale: float = 2.30) -> tuple[np.ndarray, tuple[float,float]]:
    photo,_=_assets()
    sprite=cv2.resize(photo,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
    # Pen nib tip measured directly on the source macro photograph.
    return sprite,(171*scale, 353*scale)


def _field_transform(focus: tuple[float,float], zoom: float) -> np.ndarray:
    w,h=OUTPUT_SIZE
    fx,fy=focus
    return np.array([
        [zoom, zoom*PAPER_SHEAR,
         w*.53 - zoom*(fx+PAPER_SHEAR*fy)],
        [0, zoom*PAPER_FORESHORTEN,
         h*.57 - zoom*PAPER_FORESHORTEN*fy],
    ],dtype=np.float32)


class _Ink:
    """Accumulate a nib-swept mask; never synthesize unvisited ink."""
    def __init__(self,path, size: tuple[int,int]):
        scale=WORLD_SUPERSAMPLE
        self.scale=scale
        self.size=size
        if path.artwork is not None and path.artwork.size != size:
            raise ValueError('Signature artwork must match the 720x720 paper plane')
        self.points=np.asarray(path.points,dtype=np.float64)
        self.pressures=np.asarray(path.pressures or (.6,)*len(path.points),dtype=np.float64)
        lengths=np.hypot(np.diff(self.points[:,0]),np.diff(self.points[:,1]))
        self.distances=np.r_[0,np.cumsum(lengths)]
        self.full_length=self.distances[-1]
        self.index=0
        self.last_target=0.0
        self.current=self.points[0]
        self.mask=np.zeros((size[1]*scale,size[0]*scale),dtype=np.uint8)
        self.width=max(1,int(path.reveal_width*scale))
        if path.artwork is not None:
            original=np.asarray(path.artwork.convert('L'))
            self.artwork=cv2.resize(original,(size[0]*scale,size[1]*scale),interpolation=cv2.INTER_CUBIC)
        else:
            self.artwork=None
        seed=np.random.default_rng(1803)
        self.pigment=(seed.uniform(.91,1.0,size=self.mask.shape)*255).astype(np.uint8)

    def _draw(self,a,b,pressure):
        aa=lambda p:(int(round(p[0]*self.scale)),int(round(p[1]*self.scale)))
        width=max(1,int(self.width*(.78+.32*pressure)))
        intensity=max(135,round(185+65*pressure))
        cv2.line(self.mask,aa(a),aa(b),intensity,width,cv2.LINE_AA)
        cv2.circle(self.mask,aa(b),max(1,width//2),intensity,-1,cv2.LINE_AA)

    def advance(self,fraction: float):
        """Monotone incremental deposition avoids recomputing the entire route."""
        target=min(self.full_length,max(0.,fraction*self.full_length))
        new_idx=min(len(self.points)-2,max(0,bisect_right(self.distances,target)-1))
        if target < self.last_target-1e-7:
            raise ValueError('Ink progress must not go backwards')
        self.last_target=target
        while self.index < new_idx:
            a=self.current
            b=self.points[self.index+1]
            self._draw(a,b,self.pressures[self.index])
            self.current=b
            self.index+=1
        segment=self.distances[self.index+1]-self.distances[self.index]
        u=0 if segment==0 else max(0.,min(1.,(target-self.distances[self.index])/segment))
        point=self.points[self.index]+u*(self.points[self.index+1]-self.points[self.index])
        if np.linalg.norm(point-self.current)>1e-6:
            pressure=(1-u)*self.pressures[self.index]+u*self.pressures[self.index+1]
            self._draw(self.current,point,pressure)
            self.current=point
        if target >= self.full_length-1e-5:
            self._draw(self.points[-2],self.points[-1],self.pressures[-1])
        return self.alpha()

    def alpha(self)->np.ndarray:
        if self.artwork is not None:
            # Font pixels cannot appear before the actual nib touches them.
            a=cv2.multiply(self.mask,self.artwork,scale=1/255)
        else:
            a=self.mask
        # Microscopic broken pigment edges from the physical paper fibres.
        return cv2.multiply(a,self.pigment,scale=1/255)


def _blend(base:np.ndarray, overlay:np.ndarray, opacity:np.ndarray)->np.ndarray:
    f=opacity.astype(np.float32)/255.0
    if f.ndim==2:f=f[:,:,None]
    return np.uint8(np.clip(base.astype(np.float32)*(1-f)+overlay.astype(np.float32)*f,0,255))


def _pen_layer(background:np.ndarray,nib:tuple[float,float],
               direction:tuple[float,float],seconds_after:float)->np.ndarray:
    """Real photographic nib and soft ground-contact shadow, never a vector pen."""
    sprite,anchor=_photo_sprite()
    x,y=nib
    t=max(0.,seconds_after)
    lift=min(1.,t/.34) if t>0 else 0.
    # The body moves out of the focal plane as the pen clears the finished ink.
    photo_x=x+lift*30
    photo_y=y-lift*28
    sway=np.clip(direction[1]*.012+direction[0]*.006,-.023,.023)
    # Affine rotation is around the measured metal ballpoint, not frame centre.
    ca,sa=cos(sway),sin(sway)
    a,b=anchor
    mat=np.float32([[ca,-sa,photo_x-ca*a+sa*b],
                    [sa, ca,photo_y-sa*a-ca*b]])
    h,w=background.shape[:2]
    rgba=cv2.warpAffine(sprite,mat,(w,h),flags=cv2.INTER_LINEAR,
                        borderMode=cv2.BORDER_CONSTANT,borderValue=(0,0,0,0))
    alpha=rgba[:,:,3]
    # A broad moving cast shadow plus a concentrated nib contact shadow.
    shadow=cv2.GaussianBlur(alpha,(0,0),13)
    shmat=np.float32([[1,0,21],[0,1,22]])
    shadow=cv2.warpAffine(shadow,shmat,(w,h))
    sf=np.clip(shadow.astype(np.float32)/255*.17*(1-.9*lift),0,1)
    background=np.uint8(np.clip(background.astype(np.float32)*(1-sf[:,:,None]),0,255))
    if lift<.85:
        # Elliptical soft shadow where steel meets cotton paper.
        oval=np.zeros((h,w),dtype=np.uint8)
        cv2.ellipse(oval,(int(x+8),int(y+7)),(17,7),-13,0,360,100,-1,cv2.LINE_AA)
        oval=cv2.GaussianBlur(oval,(0,0),4.5)
        contact=oval.astype(np.float32)/255*(1-lift)*.62
        background=np.uint8(np.clip(background.astype(np.float32)*(1-contact[:,:,None]),0,255))
    if t>.15:
        # Physical defocus and exit, no graphic crossfade during actual writing.
        rgba[:,:,:3]=cv2.GaussianBlur(rgba[:,:,:3],(0,0),max(0.5,lift*2.2))
    if t>.40:
        alpha=np.uint8(alpha*np.clip(1-(t-.40)/.32,0,1))
    return _blend(background,rgba[:,:,:3],alpha)


class CinematicCamera:
    def __init__(self, path):
        self.center=np.array(path.points[0],dtype=np.float64)
        if path.artwork is not None and path.artwork.getbbox():
            a,b,c,d=path.artwork.getbbox()
            self.final=np.array(((a+c)/2,(b+d)/2),dtype=np.float64)
        else:
            pts=np.asarray(path.points)
            self.final=(pts.min(axis=0)+pts.max(axis=0))/2

    def transform(self, nib, seconds_after:float)->np.ndarray:
        target=np.array(nib,dtype=np.float64)
        # Shoulder-height camera tracks ink as the wrist progresses right-to-left.
        # A stabilized macro rig follows the nib closely enough that the
        # photographic pen shaft always exits beyond the image border.
        # A lagging camera would expose the right edge of the reference plate.
        # Smooth camera inertia: follow handwriting rather than tiny
        # pixel-scale jitter. The actual nib remains anchored to the ink.
        self.center[0]+=(target[0]-self.center[0])*.16
        self.center[1]+=(target[1]-self.center[1])*.13
        blend=np.clip(seconds_after/REVEAL_SECONDS,0,1)
        blend=blend*blend*(3-2*blend)
        focus=(1-blend)*self.center+blend*self.final
        zoom=(1-blend)*MACRO_ZOOM+blend*1.32
        return _field_transform(tuple(focus),zoom)


def cinematic_frames(path,timeline:MotionTimeline|None=None,
                     *,size:tuple[int,int]=OUTPUT_SIZE)->Iterator[np.ndarray]:
    """Yield actual RGB photographs of the moving nib on an oblique paper plane."""
    if size!=OUTPUT_SIZE:
        raise ValueError('The photographic lens is calibrated for 1280x720')
    if size != OUTPUT_SIZE:
        raise ValueError('Expected a 1280x720 cinematic frame')
    motion=timeline or MotionTimeline(path)
    camera=CinematicCamera(path)
    world=_paper_world()
    xx,yy,lighting=_optical_layers()
    ink=_Ink(path,(720,720))
    last_progress=0.
    wrist=np.array((1.,0.), dtype=np.float64)
    for frame in range(ceil((motion.writing_seconds + REVEAL_SECONDS)*FRAME_RATE)):
        seconds=frame/FRAME_RATE
        state=motion.at(seconds)
        progress=max(last_progress,state.progress)
        last_progress=progress
        ink_alpha=ink.advance(progress)
        after=max(0.,seconds-motion.writing_seconds)
        transform=camera.transform(state.position,after)
        photo=cv2.warpAffine(world,transform,size,flags=cv2.INTER_LINEAR,
                             borderMode=cv2.BORDER_REFLECT_101)
        paper=np.uint8(np.clip(photo.astype(np.float32)*lighting[:,:,None],0,255))
        # Same affine transform, divided by super-sampling for ink-plane pixels.
        ink_transform=transform.copy()
        ink_transform[:,:2]/=WORLD_SUPERSAMPLE
        alpha=cv2.warpAffine(ink_alpha,ink_transform,size,
                             flags=cv2.INTER_LINEAR,borderValue=0)
        ink_rgb=np.array((30,37,126),dtype=np.uint8).reshape(1,1,3)
        result=_blend(paper,np.broadcast_to(ink_rgb,paper.shape),alpha)
        # Lens depth of field: sharp near nib, softly defocused at macro edges.
        nx=transform[0,0]*state.position[0]+transform[0,1]*state.position[1]+transform[0,2]
        ny=transform[1,1]*state.position[1]+transform[1,2]
        distance=np.sqrt(((xx-nx)*.80)**2+((yy-ny)*1.2)**2)
        blur_factor=np.clip((distance-175)/350,0,.65)
        soft=cv2.GaussianBlur(result,(0,0),2.1)
        result=np.uint8(result*(1-blur_factor[:,:,None])+soft*blur_factor[:,:,None])
        if after < .78:
            # The wrist cannot rotate instantaneously at every tiny bend.
            tangent=np.asarray(state.direction,dtype=np.float64)
            wrist=.955*wrist+.045*tangent
            norm=np.linalg.norm(wrist)
            if norm>1e-8:wrist/=norm
            result=_pen_layer(result,(nx,ny),tuple(wrist),after)
        yield np.ascontiguousarray(result)


def encode_cinematic_video(path,output:Path,
                           *,timeline:MotionTimeline|None=None)->Path:
    """Stream photographic RGB frames to FFmpeg, with no temporary image dump."""
    motion=timeline or MotionTimeline(path)
    output.parent.mkdir(parents=True,exist_ok=True)
    cmd=[
        'ffmpeg','-hide_banner','-loglevel','error','-y',
        '-f','rawvideo','-pixel_format','rgb24',
        '-video_size','1280x720','-framerate',str(FRAME_RATE),
        '-i','pipe:0','-an','-c:v','libx264',
        '-preset','slow','-crf','17','-pix_fmt','yuv420p',
        '-movflags','+faststart',str(output),
    ]
    process=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        assert process.stdin is not None
        for frame in cinematic_frames(path,motion):
            process.stdin.write(frame.tobytes())
        process.stdin.close()
        code=process.wait(timeout=120)
        error=process.stderr.read().decode('utf-8',errors='replace') if process.stderr else ''
        if code!=0:
            raise RuntimeError('Cinematic MP4 encoder failed: '+error[-1400:])
        if not output.is_file() or output.stat().st_size<1000:
            raise RuntimeError('Cinematic MP4 output is missing')
    except BaseException:
        if process.poll() is None:process.kill();process.wait()
        output.unlink(missing_ok=True)
        raise
    finally:
        if process.stderr:process.stderr.close()
    return output
