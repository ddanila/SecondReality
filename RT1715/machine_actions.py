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


def ease(time,interval):
    u=float(np.clip((time-interval[0])/(interval[1]-interval[0]),0,1))
    return u*u*u*(10-15*u+6*u*u)


def font_bitmap(text):
    # Reuse the demo repository's captured DOS ROM font, not a host font.
    path=Path(__file__).resolve().parent.parent/'GRAB/SYSFONT/FONT8X14.INC'
    rows=[[int(v)&255 for v in line.split(';')[0][3:].strip().split(',')]
          for line in path.read_text().splitlines() if line.startswith('db ')]
    im=Image.new('1',(max(1,len(text)*8),14))
    for i,char in enumerate(text):
        if not 32<=ord(char)<127:raise ValueError('Boot text must be printable ASCII')
        for y,value in enumerate(rows[ord(char)][:14]):
            for x in range(8):im.putpixel((i*8+x,y),bool(value & (128>>x)))
    return im


def text_mesh(text,x,z,glass,unit=.95):
    vertices=[];faces=[]
    for x0,y0,x1,y1 in rectangles(font_bitmap(text)):
        index=len(vertices)
        for a,b in [(x0,y1),(x1,y1),(x1,y0),(x0,y0)]:
            px=x+a*unit;pz=z-b*unit
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
    for line,entry in enumerate(settings['boot_lines']):
        source=text_mesh(entry['text'],entry.get('x',-99),entry['z'],glass,settings.get('font_unit',.95))
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
        angle=math.pi/2*ease(time,settings['close']);c,s=math.cos(angle),math.sin(angle)
        rotation=np.array([[c,0,s],[0,1,0],[-s,0,c]])
        result[:3]=np.rint(pivot-rotation@pivot).astype(int)
        result[3:]=np.rint(rotation.flatten()*16384).astype(int)
    return tuple(result)


def visible(label,time,settings):
    if label.startswith('disk-'):return time<=settings['close'][1]+.1
    if label=='boot-led':
        return settings['close'][1]<=time<settings['ready'] and int(time*6)%3!=2
    if label.startswith('boot-'):
        line=int(label.split('-')[1]);entry=settings['boot_lines'][line]
        if time<entry['time'] or time>=entry.get('until',1e9):return False
        if entry.get('blink'):return int((time-entry['time'])*2)%2==0
    return True
