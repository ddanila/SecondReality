"""Source triangles and flight-end camera for the live chapter renderer."""
import json
import struct
import numpy as np


def write(path, records, load, chips, keys, flight_path):
    from robotron_lod import exterior
    from robotron import COLORS
    parts=[(name,m,COLORS[color][1],2 if name=='screen' else 0)
           for name,m,color in exterior()]
    for name,r in records.items():
        if name.startswith(('logic-boards-', 'fascia', 'drives', 'drive-', 'pedestal')):
            group=(4 if 'display-controller' in name else 1) if name.startswith('logic-boards-') else (3 if name.startswith(('drives','drive-')) else 0)
            parts.append((name,load(r),r.get('color','#999999'),group))
    for n,m in enumerate(keys):parts.append(('key'+str(n),m,'#dddccb',0))
    for inst,body,leads in chips:
        parts.extend([(inst['id'],body,'#34383b',4 if inst['board']=='display-controller' else 1),(inst['id']+'-pins',leads,'#aaa99b',4 if inst['board']=='display-controller' else 1)])
    bases=np.array([[201,193,167],[187,194,194],[56,116,91],[30,34,35],[145,181,197],[221,220,203],[182,65,57],[120,95,65]])
    palette=(bases[:,None,:]*np.linspace(.25,1,8)[None,:,None]).reshape(64,3)
    triangles=[]
    for name,mesh,color,group in parts:
        # Preserve complete surfaces; simplify curvature, never drop random faces.
        mesh.merge_vertices(digits_vertex=3)
        if (group in (1,3,4) or name.startswith('key')) and len(mesh.faces)>80:
            mesh=mesh.simplify_quadric_decimation(face_count=min(1200 if group==0 else 240,max(48,int(len(mesh.faces)*.025))),aggression=10)
        rgb=tuple(int(color.lstrip('#')[i:i+2],16) for i in (0,2,4))
        for vertices,normal in zip(mesh.triangles,mesh.face_normals):
            shade=.4+.6*max(0,float(np.dot(normal,np.array([-.3,-.5,.812]))))
            index=192+int(np.argmin(np.sum((palette-np.array(rgb)*shade)**2,axis=1)))
            triangles.append(struct.pack('<9h2B',*np.rint(vertices.flatten()*8).astype(int),index,group))
    if len(triangles)>250000:raise ValueError('Chapter mesh exceeds live renderer budget')
    flight=json.loads(flight_path.read_text());closing=flight['screen_return']
    camera=closing['eye']+closing['target']
    from PIL import Image
    boot=np.asarray(Image.open(flight_path.parent/'boot/prompt.png').convert('L'))
    path.write_bytes(struct.pack('<I6f',len(triangles),*camera)+b''.join(triangles)+(boot>127).astype('uint8').tobytes())
    return {'triangles':len(triangles),'parts':len(parts),'camera':camera,'method':'source surfaces with quadric simplification; no bounding-box substitutes'}
