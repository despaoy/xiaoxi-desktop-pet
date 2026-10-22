"""Runtime optical-flow animation renderer. Source art is never overwritten.

Cache is an expendable rendering product, not a replacement for the art source.
"""
import hashlib
import json
import math
from pathlib import Path
import sys
import time

BASE = Path(__file__).resolve().parent.parent
runtime = BASE / '.runtime'
if runtime.is_dir():
    sys.path.insert(0, str(runtime))

import cv2
import numpy as np
from PIL import Image, ImageTk

RENDER_VERSION = 'flow-v4-60fps'
SIZE = 304
FPS = 60
IDLE_FRAMES = round(4.5 * FPS)


def ease(t):
    return t*t*(3-2*t)


def normalize_cell(cell):
    rgba = np.array(cell.convert('RGBA'))
    alpha = rgba[:,:,3]
    # Discard detached generation debris, keeping the connected character silhouette.
    solid = (alpha > 160).astype(np.uint8)
    connected = cv2.dilate(solid, np.ones((3,3),np.uint8))
    count, labels, stats, _ = cv2.connectedComponentsWithStats(connected, 8)
    if count <= 1:
        raise ValueError('素材格没有可见角色')
    largest = 1 + np.argmax(stats[1:,cv2.CC_STAT_AREA])
    keep = cv2.dilate((labels == largest).astype(np.uint8),np.ones((3,3),np.uint8))
    alpha = np.where(keep,alpha,0).astype(np.uint8)
    alpha[alpha < 64] = 0
    rgba[:,:,3] = alpha
    ys,xs = np.where((alpha > 160) & (labels == largest))
    x0,x1,y0,y1 = xs.min(),xs.max()+1,ys.min(),ys.max()+1
    cropped = Image.fromarray(rgba).crop((x0,y0,x1,y1))
    target_height = SIZE-26
    scale = min(target_height/cropped.height,(SIZE-20)/cropped.width)
    cropped = cropped.resize((round(cropped.width*scale),round(cropped.height*scale)),Image.Resampling.LANCZOS)
    result = Image.new('RGBA',(SIZE,SIZE))
    result.alpha_composite(cropped,((SIZE-cropped.width)//2,SIZE-12-cropped.height))
    return np.array(result).astype(np.float32)/255


def prepare(atlas, columns=4, rows=4):
    im = Image.open(atlas).convert('RGBA')
    return [normalize_cell(im.crop((round(c*im.width/columns),round(r*im.height/rows),round((c+1)*im.width/columns),round((r+1)*im.height/rows)))) for r in range(rows) for c in range(columns)]


def flow_gray(a):
    rgb = a[:,:,:3]*a[:,:,3:4] + 0.55*(1-a[:,:,3:4])
    return cv2.cvtColor((rgb*255).astype(np.uint8),cv2.COLOR_RGB2GRAY)


def compute_pair(a,b):
    solver = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_MEDIUM)
    solver.setUseSpatialPropagation(True)
    g0,g1 = flow_gray(a),flow_gray(b)
    forward = solver.calc(g0,g1,None)
    backward = solver.calc(g1,g0,None)
    return forward,backward


def tween(a,b,pair,t):
    if t <= 0: return a.copy()
    if t >= 1: return b.copy()
    forward,backward = pair
    yy,xx = np.mgrid[:SIZE,:SIZE].astype(np.float32)
    # Warp premultiplied RGBA to avoid dark fringes in translucent edges.
    def warp(im,flow,factor):
        pre = im.copy()
        pre[:,:,:3] *= pre[:,:,3:4]
        return cv2.remap(pre,xx-factor*flow[:,:,0],yy-factor*flow[:,:,1],cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)
    left = warp(a,forward,t)
    right = warp(b,backward,1-t)
    out = (1-t)*left+t*right
    out[:,:,:3] /= np.maximum(out[:,:,3:4],1e-6)
    return np.clip(out,0,1)


def breathe(frame,phase):
    # Foot anchored, subpixel-scale breathing, without a whole-body vertical bob.
    scale = 1+0.0035*math.sin(phase*2*math.pi)
    matrix = np.float32([[1,0,0],[0,scale,(SIZE-12)*(1-scale)]])
    return cv2.warpAffine(frame,matrix,(SIZE,SIZE),flags=cv2.INTER_LINEAR,borderMode=cv2.BORDER_CONSTANT)


def rgba_bytes(frame):
    return (np.clip(frame,0,1)*255+0.5).astype(np.uint8)


def render_sequences(atlas):
    poses = prepare(atlas)
    pairs = {}
    def interpolate(a,b,t):
        key = (a,b)
        if key not in pairs:
            pairs[key] = compute_pair(poses[a],poses[b])
        return tween(poses[a],poses[b],pairs[key],ease(t))
    sequences = {}
    idle = []
    # Keep the entire character stable; blinking affects only the eye region.
    yy,xx = np.mgrid[:SIZE,:SIZE]
    eye_mask = np.exp(-(((xx-SIZE*.50)/(SIZE*.19))**8 + ((yy-SIZE*.385)/(SIZE*.085))**8))[:,:,None].astype(np.float32)
    for n in range(IDLE_FRAMES):
        sec = n/FPS
        blink = 0
        if 3.0 <= sec < 3.10: blink = (sec-3.0)/.10
        elif 3.10 <= sec < 3.16: blink = 1
        elif 3.16 <= sec < 3.30: blink = 1-(sec-3.16)/.14
        f = poses[0].copy()
        if blink:
            blink_frame = interpolate(0,2,blink)
            f = f*(1-eye_mask)+blink_frame*eye_mask
        idle.append(rgba_bytes(breathe(f,n/IDLE_FRAMES)))
    sequences['idle'] = np.stack(idle)
    # Durations are transitions, not slideshow holds. Start and finish on one shared idle.
    plans = {
        'click':[(0,5,.32),(5,6,.36),(6,6,.08),(6,0,.42)],
        'reminder':[(0,8,.24),(8,9,.32),(9,10,.22),(10,9,.25),(9,10,.22),(10,9,.25),(9,8,.32),(8,0,.35)],
        'success':[(0,12,.30),(12,13,.22),(13,14,.22),(14,13,.20),(13,14,.25),(14,0,.45)]
    }
    for name,segments in plans.items():
        result=[]
        for a,b,seconds in segments:
            count=max(2,round(seconds*FPS))
            for n in range(count):
                frame=poses[a].copy() if a==b else interpolate(a,b,n/count)
                result.append(rgba_bytes(frame))
        result.append(rgba_bytes(poses[0]))
        sequences[name]=np.stack(result)
    return poses,sequences


class SmoothPlayer:
    def __init__(self,root,path,display_size=304):
        self.path=Path(path)
        self.config=json.loads(self.path.read_text(encoding='utf-8'))
        atlas=(self.path.parent/self.config['atlas']).resolve()
        if not atlas.is_relative_to(self.path.parent.resolve()):
            raise ValueError('角色素材路径超出角色包')
        digest=hashlib.sha256(atlas.read_bytes()+RENDER_VERSION.encode()).hexdigest()[:16]
        folder=BASE/'data'/'render-cache'
        folder.mkdir(parents=True,exist_ok=True)
        cache=folder/(digest+'.npz')
        try:
            with np.load(cache,allow_pickle=False) as saved:
                arrays={name:saved[name] for name in self.config['actions']}
        except (OSError,ValueError,KeyError):
            _,arrays=render_sequences(atlas)
            temporary=cache.with_suffix('.tmp.npz')
            np.savez_compressed(temporary,**arrays)
            temporary.replace(cache)
        self.frames=[]  # Legacy API used by smoke and original-frame comparison.
        self.clips={}
        for name,array in arrays.items():
            clip=[]
            for f in array:
                image=Image.fromarray(f)
                if display_size != SIZE:
                    image=image.resize((display_size,display_size),Image.Resampling.LANCZOS)
                clip.append(ImageTk.PhotoImage(image,master=root))
            self.clips[name]=clip
        self.frames=self.clips['idle']
        self.state='idle'
        self.started=time.monotonic()
        self.paused_at=None
        self.speed=1.0
        self.timeline=self  # compatibility with existing preview code
        self.pending=None

    def cursor(self):
        import copy
        cursor=copy.copy(self)
        cursor.started=time.monotonic()
        return cursor

    def play(self,action):
        if action not in self.clips: return False
        # Repeated user clicks should not continually rewind the same active motion.
        if self.state==action and action!='idle' and ((self.paused_at if self.paused_at is not None else time.monotonic())-self.started)*self.speed<len(self.clips[action])/FPS:
            return True
        if self.state!='idle':
            self.pending=action
            return True
        self.state=action
        self.started=time.monotonic()
        return True

    def pause(self,paused):
        if paused and self.paused_at is None:
            self.paused_at=time.monotonic()
        elif not paused and self.paused_at is not None:
            self.started+=time.monotonic()-self.paused_at
            self.paused_at=None

    def image(self,focused=False):
        now=self.paused_at if self.paused_at is not None else time.monotonic()
        index=int((now-self.started)*FPS*self.speed)
        if self.state!='idle' and index>=len(self.clips[self.state]):
            self.state=self.pending or 'idle'
            self.pending=None
            self.started=now
            index=0
        if focused and self.state=='idle': index=0
        return self.clips[self.state][index%len(self.clips[self.state])]


if __name__=='__main__':
    atlas=BASE/'assets/characters/silver-dragon/animations/atlas-v1.png'
    poses,clips=render_sequences(atlas)
    print({k:len(v) for k,v in clips.items()})
    digest=hashlib.sha256(atlas.read_bytes()+RENDER_VERSION.encode()).hexdigest()[:16]
    folder=BASE/'data/render-cache'
    folder.mkdir(parents=True,exist_ok=True)
    np.savez_compressed(folder/(digest+'.npz'),**clips)
