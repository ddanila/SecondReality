"""Full-cut key-wall reveal, leaving the accepted short runtime untouched."""
import json
from pathlib import Path
import numpy as np
import animation,robotron
from build import HERE


def build(dos,bake_cache=True):
    dos=Path(dos)
    mapping=animation.mapping((dos/'U2E.00M').read_bytes())
    frames=animation.decode((HERE/'build/dos/U2E.0AB').read_bytes(),len(mapping))
    states=[[0]*12 for _ in mapping];visible=[False]*len(mapping)
    poses=[];visibility=[];fovs=[]
    flight=json.loads((HERE/'assets/robotron/flight.json').read_text())
    start_eye=np.array([-228.5,-370.5,34.5]);start_target=np.array([-215.,-370.5,34.5])
    for index,(records,fov) in enumerate(frames):
        for r in records:states[r['object']]=list(r['state']);visible[r['object']]=r['visible']
        pose=[list(s) for s in states];on=list(visible);t=index/flight['fps']
        if t<5:
            u=t/5;w=u*u*u*(10-15*u+6*u*u)
            eye,target=robotron.sample(flight,t)
            def ease(x):
                x=np.clip(x,0,1);return x*x*x*(10-15*x+6*x*x)
            # Retreat and rise outside the cap before joining the channel;
            # a direct blend crosses through the key's solid side wall.
            retreat=start_eye+np.array([-18*ease(t/1.5),-12*ease(t/2),24*ease(t/1.2)])
            join=ease((t-2)/3)
            pose[0]=robotron.camera(retreat*(1-join)+eye*join,start_target*(1-join)+target*join)
            on=[True]*len(mapping)
            fov=round((35*(1-w)+flight['fov']*w)*256/360)
        poses.append(pose);visibility.append(on);fovs.append(fov)
    # Encode exact per-frame projection values after generating the deltas.
    raw=bytearray(robotron.encode_animation(poses,visibility,flight['fov']))
    decoded=animation.decode(raw,len(mapping));at=0
    for i,(records,_) in enumerate(decoded):
        for r in records:at+=2+len(r['payload'])
        if raw[at]!=255:raise ValueError('Animation marker offset mismatch')
        raw[at+1]=fovs[i];at+=2
    (dos/'U2E.0AB').write_bytes(raw)
    (dos/'U2E.KEY').write_text('7 8 9\n')
    (dos.parent/'key-wall-reveal.json').write_text(json.dumps({'seconds':5,'eye':start_eye.tolist(),'target':start_target.tolist(),'start_fov':35,'end_fov':flight['fov'],'remaining_route':'unchanged','standalone_cut':'untouched'},indent=2)+'\n')
    from route_cache import build as route
    from bake import bake
    if bake_cache:route(dos);bake(dos)
    return dos
