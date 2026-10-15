"""Bake conservative per-pose draw lists using the DOS integer transforms.

No visibility is inferred between samples: every encoded animation pose gets a
list. Geometry, material mapping and animation fingerprint invalidate the cache.
This removes runtime bounds tests and sorting, not hidden-surface depth tests.
"""
import argparse
import json
from pathlib import Path
import re
import struct
import animation
import scene


def fnv(data, h=2166136261):
    for value in data:h=((h^value)*16777619)&0xffffffff
    return h


def signed(n, bits=32):
    n &= (1<<bits)-1
    return n-(1<<bits) if n&(1<<(bits-1)) else n


def compose(a,b):
    # States store translation before the row-major 14-bit matrix.
    return [signed((sum(a[3+r*3+k]*b[k] for k in range(3))>>14)+a[r]) for r in range(3)]+[
        signed(sum(a[3+r*3+k]*b[3+k*3+c] for k in range(3)))>>14 for r in range(3) for c in range(3)]


def outside(bounds,r,px,py):
    lo=[];hi=[]
    for axis in range(3):
        m=[signed(v,16) for v in r[3+axis*3:6+axis*3]]
        center=sum(m[k]*(bounds[k][0]+bounds[k][1]) for k in range(3))
        radius=sum(abs(m[k])*(bounds[k][1]-bounds[k][0]) for k in range(3))
        lo.append(((center-radius)>>15)+r[axis]);hi.append(((center+radius)>>15)+r[axis])
    return (hi[2]<512 or lo[2]>9999999 or hi[0]*px+160*hi[2]<0 or
            -lo[0]*px+161*hi[2]<0 or hi[1]*py+75*hi[2]<0 or -lo[1]*py+76*hi[2]<0)


def build(dos):
    materials=(dos/'U2E.00M').read_bytes();mapping=animation.mapping(materials)
    digest=fnv(materials);meshes={};centers={};bounds={}
    for slot in dict.fromkeys(mapping[1:]):
        data=(dos/f'U2E.{slot:03}').read_bytes();digest=fnv(data,digest)
        mesh=scene.decode(data);meshes[slot]=mesh
        centers[slot]=struct.unpack_from('<H',dict(scene.blocks(data))[b'ORD0'],2)[0]
        bounds[slot]=[(min(v[k] for v in mesh['vertices']),max(v[k] for v in mesh['vertices'])) for k in range(3)]
    data=(dos/'U2E.0AB').read_bytes();digest=fnv(data,digest)
    frames=animation.decode(data,len(mapping));states=[[0]*12 for _ in mapping];visible=[False]*len(mapping)
    source=(Path(__file__).resolve().parents[1]/'VISU/AVISTAN.INC').read_text(encoding='cp437')
    tangent=[int(n) for row in source.splitlines() if row.startswith('dw ') for n in re.findall(r'\d+',row)]
    rows=[];considered=0
    for records,fov in frames:
        for record in records:
            states[record['object']]=record['state'];visible[record['object']]=record['visible']
        half=max(512,min(16383,(fov<<8)//2));px=160*tangent[half>>6]>>8;py=px*225>>8
        entries=[]
        for i,slot in enumerate(mapping[1:],1):
            if not visible[i]:continue
            considered+=1;r=compose(states[0],states[i])
            if outside(bounds[slot],r,px,py):continue
            mesh=meshes[slot];v=mesh['vertices'][centers[slot]]
            distance=1000000000 if mesh['name'][1:2]=='_' else signed((sum(r[9+k]*v[k] for k in range(3))>>14)+r[2])
            entries.append((distance,i))
        rows.append(bytes([i for _,i in sorted(entries)]))
    offsets=[0]
    for row in rows:offsets.append(offsets[-1]+len(row))
    payload=struct.pack('<4sIII',b'RV01',digest,len(rows),len(mapping))+struct.pack(f'<{len(offsets)}I',*offsets)+b''.join(rows)
    (dos/'U2E.VIS').write_bytes(payload)
    report={'version':1,'fingerprint':f'{digest:08x}','poses':len(rows),'objects':len(mapping),
            'active_object_poses':considered,'retained_object_poses':sum(map(len,rows)),'bytes':len(payload),
            'method':'exact encoded poses; conservative integer AABB frustum rejection; stable front-to-back order'}
    (dos.parent/'route-cache.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dos-dir',type=Path,default=Path(__file__).parent/'build/dos')
    print(json.dumps(build(p.parse_args().dos_dir),indent=2))
