"""Small front-panel ink meshes, shared by flight and credit photographs."""
import trimesh
import json
from pathlib import Path
HERE=Path(__file__).resolve().parent
from legends import bitmap, rectangles
from PIL import Image


def badge_bitmap():
    with Image.open(HERE/'assets/robotron/badge.png') as im:return im.copy()


def markings(solid=False):
    # White badge follows the owner photograph below the left drive.
    badge=json.loads((HERE/'assets/robotron/badge.json').read_text())['placement_mm']
    for name,text,cx,z,height,y in [
        ('model-name','robotron 1715 M',badge['center_x'],badge['center_z'],badge['height'],badge['y']),
        ('reset-label','RESET',-208,4.8,3.2,-200.12),
        ('power-label','POWER',207,4.8,3.2,-200.12),
        ('off-label','OFF',175,17,3,-200.12),
        ('on-label','ON',238,17,3,-200.12),
    ]:
        ink=badge_bitmap() if name=='model-name' else bitmap([text]);unit=height/ink.height
        ux=badge['width']/ink.width if name=='model-name' else unit
        vertices=[];faces=[];pieces=[]
        for x0,y0,x1,y1 in rectangles(ink):
            left=cx+(x0-ink.width/2)*ux;right=cx+(x1-ink.width/2)*ux
            top=z+(ink.height/2-y0)*unit;bottom=z+(ink.height/2-y1)*unit
            if solid:
                part=trimesh.creation.box(extents=[right-left,.04,top-bottom])
                part.apply_translation([(left+right)/2,y+.02,(bottom+top)/2]);pieces.append(part)
            n=len(vertices)
            vertices.extend([(left,y,bottom),(right,y,bottom),(right,y,top),(left,y,top)])
            faces.extend([(n,n+1,n+2),(n,n+2,n+3)])
        mesh=trimesh.util.concatenate(pieces) if solid else trimesh.Trimesh(vertices,faces,process=True)
        faces=mesh.faces
        # Scene objects have a 500-vertex limit, including separate glyphs.
        chunk=384 if solid else 160
        for i in range(0,len(faces),chunk):
            yield f'{name}-{i//chunk}',mesh.submesh([range(i,min(i+chunk,len(faces)))],append=True),('white' if name=='model-name' else 'black'),'marking'
