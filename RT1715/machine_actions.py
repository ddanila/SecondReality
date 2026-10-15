"""Authored disk loading and CRT startup, baked into the music-clock scene."""
from pathlib import Path
import math
import numpy as np
import trimesh
from PIL import Image
from legends import rectangles
from keycaps import hits
from source_geometry import chunks
from monitor_geometry import crt_surround

IDENTITY=(16384,0,0,0,16384,0,0,0,16384)
BOOT=Path(__file__).resolve().parent/'assets/robotron/boot'


def ease(time,interval):
    u=float(np.clip((time-interval[0])/(interval[1]-interval[0]),0,1))
    return u*u*u*(10-15*u+6*u*u)


def bitmap_mesh(bitmap,x,z,glass,pixel_size):
    vertices=[];faces=[]
    for x0,y0,x1,y1 in rectangles(bitmap):
        index=len(vertices)
        for a,b in [(x0,y1),(x1,y1),(x1,y0),(x0,y0)]:
            px=x+a*pixel_size[0];pz=z-b*pixel_size[1]
            distance=hits(glass,np.array([px,-200.,pz]),np.array([0.,1.,0.]))
            if not len(distance):raise ValueError('Boot text extends outside CRT')
            vertices.append((px,-200+min(distance)-1.0,pz))
        faces.extend([(index,index+1,index+2),(index,index+2,index+3)])
    return trimesh.Trimesh(vertices,faces,process=True)


def objects(load,records,data,settings):
    unit=settings['drive'];glass=crt_surround(data['screen'])[0]
    for part,color in [('drive-diskette','dark'),('drive-medium','dark'),('drive-diskette-label','white')]:
        source=load(records[f'{part}-{unit}'])
        # Retain the jacket openings, medium and label; only subpixel welds.
        for i,m in enumerate(chunks(source,precision=(.1,.1,.02))):
            yield f'disk-{part}-{i}',m,color,'machine-disk'
    for line,entry in enumerate(settings['boot_frames']):
        screen=settings['screen']
        with Image.open(BOOT/entry['image']) as bitmap:
            source=bitmap_mesh(bitmap,screen['x'],screen['z'],glass,
                               (screen['width']/640,screen['height']/288))
        for i,m in enumerate(chunks(source,faces_per_chunk=80,precision=(.001,.001,.001))):
            yield f'boot-{line}-{i}',m,'pcb','machine-text'
    # Lit overlay over the existing source drive LED; the unlit housing stays.
    led=load(records[f'drive-led-{unit}'])
    led.vertices[:,1]-=.25
    yield 'boot-led',led,'red','machine-led'


def pose(label,base,time,settings,data):
    result=list(base)
    if label.startswith('disk-'):
        result[1]-=round((1-ease(time,settings['insert']))*settings['withdraw_mm']*64)
    if label.startswith(f"src-drive-latch-{settings['drive']}-"):
        pivot=np.array(next(d for d in data['driveMotion'] if d['unit']==settings['drive'])['latchPivot'])*64
        # Source hub overlaps the insertion plane. Raise the complete lever
        # above the slot, then swing its tip from +Z (open) to -Z (closed).
        lift=np.array([0,0,settings['latch_lift_mm']*64])
        angle=math.pi*(ease(time,settings['close'])-.5);c,s=math.cos(angle),math.sin(angle)
        rotation=np.array([[c,0,s],[0,1,0],[-s,0,c]])
        result[:3]=np.rint(pivot+lift-rotation@pivot).astype(int)
        result[3:]=np.rint(rotation.flatten()*16384).astype(int)
    return tuple(result)


def visible(label,time,settings):
    if label.startswith('disk-'):return time<=settings['close'][1]+.1
    if label=='boot-led':
        return settings['close'][1]<=time<settings['ready'] and int(time*6)%3!=2
    if label.startswith('boot-'):
        line=int(label.split('-')[1]);entry=settings['boot_frames'][line]
        if time<entry['time'] or time>=entry.get('until',1e9):return False
        if entry.get('blink'):return int((time-entry['time'])*2)%2==0
    return True
