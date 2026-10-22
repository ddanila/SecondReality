"""Opening diskette: original flight tracks with a replacement mothership mesh."""
import json
import hashlib
import struct
from pathlib import Path
import numpy as np
import trimesh
import scene
from build import HERE,ROOT


def build(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    old=scene.decode((ROOT/'MAIN/DATA/U2A.002').read_bytes())
    # The small pursuing craft (slot 1) retains its original mesh and path.
    # Build the jacket openings explicitly: mesh decimation filled these in
    # and removed the features that identify a 5.25-inch diskette at VGA scale.
    from shapely.geometry import Point, box
    def circle(x,y,r):return Point(x,y).buffer(r,quad_segs=3)
    outline=box(-66.675,-66.675,66.675,66.675)
    outline=outline.difference(box(61,25,68,34)) # write-protect notch
    hub=circle(0,0,14)
    slot=box(-7,-58,7,-28).union(circle(0,-58,7)).union(circle(0,-28,7))
    index=circle(23,-13,2.5)
    jacket=outline.difference(hub.union(slot).union(index))
    parts=[]
    def solid(shape,z,depth,color):
        mesh=trimesh.creation.extrude_polygon(shape,depth,engine='earcut')
        mesh.apply_translation((0,0,z));parts.append((mesh,color))
    solid(jacket,-1.2,2.4,8)
    # Exposed magnetic medium and hub reinforcement; the center stays open.
    medium=slot.union(hub).union(index).difference(circle(0,0,12))
    for part in getattr(medium,"geoms",[medium]):solid(part,-.18,.36,2)
    # Single visible label surfaces avoid hidden coplanar back faces.
    def label(x0,y0,x1,y1,z,color,side):
        vertices=[(x0,y0,z),(x1,y0,z),(x1,y1,z),(x0,y1,z)]
        faces=[[0,1,2],[0,2,3]]
        if side<0:faces=[f[::-1] for f in faces]
        parts.append((trimesh.Trimesh(vertices=vertices,faces=faces,process=False),color))
    for side in (-1,1):
        z=side*1.35
        label(-52,32,52,60,z,28,side)
        label(-52,51,52,57,z+side*.18,16,side)
        for y in (38,44):label(-44,y,27,y+1.8,z+side*.18,8,side)
    bounds=np.array(old['bounds']);origin=bounds.mean(1)
    factor=min((bounds[:,1]-bounds[:,0])[:2]/133.35)
    triangles=[];colors=[]
    angle=np.deg2rad(15);rotation=np.array([[1,0,0],[0,np.cos(angle),-np.sin(angle)],[0,np.sin(angle),np.cos(angle)]])
    # Keep a shallow flight attitude; a small bank reveals the jacket details
    # without presenting the disk face-on like the first draft.
    for mesh,color in parts:
        triangles.extend(np.rint((mesh.triangles@rotation.T)*factor+origin).astype(int).tolist())
        colors.extend([color]*len(mesh.faces))
    (output/'U2A.002').write_bytes(scene.encode(old['name'],[[tuple(v) for v in face] for face in triangles],color=8,shades=1,face_colors=colors))
    # Retain the original trailing flare object: the old rasterizer does not
    # safely accept an empty or degenerate object in this animated slot.
    (output/'U2A.003').write_bytes((ROOT/'MAIN/DATA/U2A.003').read_bytes())
    (output/'space.json').write_text(json.dumps({'replaced_slot':2,'pursuer_slot_1':'unchanged','animation':'unchanged original U2A tracks','explosion':'unchanged original PAM cue and animation','faces':len(triangles),'source':'explicit 133.35 mm 5.25-inch jacket with hub, head slot, index hole, write-protect notch and double-sided label','local_pitch_degrees':15},indent=2)+'\n')
    return output

if __name__=='__main__':print(build(HERE/'build/full-space'))


def patch_player(released,output):
    """Select the existing VGA-initializing driver at the original flight cue.

    Mode 3 omits VGA initialization and inherits the opening's register state.
    Mode 1 sets the same projection/window values after resetting mode 13h.
    The released caller still waits for its original music cue before this call.
    """
    import re,hashlib
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    data=bytearray(Path(released).read_bytes())
    pattern=rb'\x3d\x01\x00\x75\x03\xe8..\x3d\x0b\x00\x75\x03\xe8..\x3d\x02\x00\x75\x03\xe8..\x3d\x03\x00\x75\x03\xe8..'
    matches=list(re.finditer(pattern,data,re.S))
    if len(matches)!=1:raise ValueError('Released U2A video-driver selector changed')
    start=matches[0].start();normal=start+5;inherit=start+29
    target=normal+3+struct.unpack_from('<h',data,normal+1)[0]
    old=bytes(data[inherit+1:inherit+3]);struct.pack_into('<h',data,inherit+1,target-(inherit+3))
    exe=output/'U2A.EXE';exe.write_bytes(data)
    (output/'player-patch.json').write_text(json.dumps({'source_sha256':hashlib.sha256(Path(released).read_bytes()).hexdigest(),'offset':inherit+1,'before':old.hex(),'after':data[inherit+1:inherit+3].hex(),'change':'Mode 3 dispatch calls existing mode 1 initializer; original music wait and projection retained.'},indent=2)+'\n')
    return exe
