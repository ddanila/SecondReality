"""Source-model front view and exact CRT mask for the screen-entry transition."""
import hashlib
import json
from pathlib import Path
import struct
import numpy as np
from PIL import Image
from prepare import openscad


def prepare(output,records,load,keys,command='openscad'):
    import trimesh
    output=Path(output)
    prefixes=['case-base','case-lid','fascia','drives','drive-insets','drive-latch',
              'monitor-shell-lower','monitor-shell-upper','bezel','crt-glass','pedestal','keyboard-shell','keyboard-deck']
    parts=[]
    for name,record in records.items():
        if any(name==p or name.startswith(p+'-') for p in prefixes):
            parts.append((name,load(record),record.get('color','#999999')))
    parts.append(('keys',trimesh.util.concatenate(keys),'#dddccb'))
    signature=hashlib.sha256(Path(__file__).read_bytes())
    for name,mesh,color in parts:signature.update(name.encode()+color.encode()+mesh.vertices.tobytes()+mesh.faces.tobytes())
    key=signature.hexdigest();stamp=output/'crt-transition.sha256'
    target=output/'FX.CRT'
    if target.exists() and stamp.exists() and stamp.read_text()==key:return target
    scripts=[[],[]]
    for i,(name,mesh,color) in enumerate(parts):
        path=output/f'crt-source-{i}.stl';mesh.export(path)
        for k in range(2):
            tint=color if k==0 else ('#ff00ff' if name=='crt-glass' else '#101010')
            scripts[k].append(f'color("{tint}") import({json.dumps(str(path))});')
    images=[]
    for label,lines in zip(['machine','mask'],scripts):
        scad=output/f'crt-{label}.scad';png=output/f'crt-{label}.png';scad.write_text('\n'.join(lines)+'\n')
        openscad(command,scad,png,['--render','--colorscheme','Tomorrow Night','--projection','o',
                 '--imgsize','640,480','--camera','0,0,240,90,0,0,1400','--viewall','--autocenter'])
        images.append(Image.open(png).convert('RGB').resize((640,400),Image.Resampling.LANCZOS))
    raw=np.asarray(images[0]).copy();raw[np.all(raw==[29,31,33],axis=2)]=0
    lum=raw @ np.array([.2126,.7152,.0722])
    pixels=np.where(lum<2,0,np.clip(np.rint(lum*119/255)+8,8,127)).astype('uint8')
    mask=np.asarray(images[1]).astype(int)
    mask=((mask[:,:,0]>mask[:,:,1]*2+30)&(mask[:,:,2]>mask[:,:,1]*2+30)).astype('uint8')
    yy,xx=np.where(mask)
    if len(xx)<1000:raise ValueError('Source CRT is hidden in front projection')
    target.write_bytes(struct.pack('<2f',float(xx.mean()),float(yy.mean()))+pixels.tobytes()+mask.tobytes())
    stamp.write_text(key)
    return target
