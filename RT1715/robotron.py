"""Prepare the canonical Robotron assembly and an authored DOS fly-through.

Uses the OpenSCAD browser exports in the sibling 3d-models repository. Those
exports retain the canonical millimetre coordinate system (X right/Y back/Z up).
"""
import hashlib
import json
import math
from pathlib import Path
import struct

import numpy as np
import trimesh
import scene
import keycaps
from robotron_lod import exterior, keycap
from PIL import Image, ImageOps
from prepare import openscad

HERE = Path(__file__).resolve().parent
SCALE = 64  # DOS near plane 512 becomes 8 mm; limits 16-bit projected-coordinate overflow.
IDENTITY = (16384,0,0,0,16384,0,0,0,16384)
# Keep the original drone's palette entries 0..31 and 160..251 untouched.
COLORS = {'dark':(32,'#596369'), 'paint':(48,'#c9c1a7'), 'pcb':(64,'#38745b'),
          'metal':(80,'#bbc2c2'), 'black':(96,'#080a0a'), 'red':(112,'#b64139'),
          'blue':(128,'#91b5c5'), 'white':(144,'#dddccb')}

def polygons(mesh):
    """Join adjacent coplanar triangles only when their union is a convex quad."""
    vertices=np.rint(mesh.vertices*SCALE).astype(int)
    faces=[tuple(int(v) for v in face) for face in mesh.faces]
    edges={}
    for i,face in enumerate(faces):
        for a,b in zip(face,face[1:]+face[:1]):
            edges.setdefault((min(a,b),max(a,b)),[]).append(i)
    used=set(); result=[]
    for i,face in enumerate(faces):
        if i in used: continue
        a,b,c=vertices[list(face)]; normal=np.cross(b-a,c-a)
        if not np.any(normal): continue
        quad=None
        for u,v in zip(face,face[1:]+face[:1]):
            for j in edges[(min(u,v),max(u,v))]:
                if j==i or j in used: continue
                other=faces[j]
                if len(set(face+other))!=4: continue
                points=vertices[list(other)]
                n2=np.cross(points[1]-points[0],points[2]-points[0])
                if np.dot(normal,n2)<=0: continue
                if any(abs(float(np.dot(p-a,normal)))>0.1*np.linalg.norm(normal) for p in points): continue
                boundary=[(x,y) for f in (face,other) for x,y in zip(f,f[1:]+f[:1])
                          if {x,y}!={u,v}]
                chain=[boundary[0][0]]
                for _ in range(3):
                    nexts=[y for x,y in boundary if x==chain[-1]]
                    if len(nexts)!=1: break
                    chain.append(nexts[0])
                if len(set(chain))!=4: continue
                p=vertices[chain]
                if any(np.dot(np.cross(p[(k+1)%4]-p[k],p[(k+2)%4]-p[(k+1)%4]),normal)<=0
                       for k in range(4)): continue
                quad=chain;used.add(j);break
            if quad: break
        used.add(i)
        result.append([tuple(int(v) for v in p) for p in vertices[quad or list(face)]])
    return result


def camera(eye, target):
    eye, target = np.array(eye,dtype=float), np.array(target,dtype=float)
    forward = target-eye
    forward /= np.linalg.norm(forward)
    right = np.cross(forward,[0,0,1.0]); right /= np.linalg.norm(right)
    down = np.cross(forward,right)
    rotation = np.array([right,down,forward])
    return tuple(np.rint(-rotation @ eye*SCALE).astype(int)) + tuple(
        np.rint(rotation.flatten()*16384).astype(int))


def sample_track(keys, time, field):
    """Time-aware Hermite track; quintic mode also keeps acceleration continuous."""
    for i,(left,right) in enumerate(zip(keys,keys[1:])):
        if time <= right['time']:
            dt=right['time']-left['time']
            u=max(0,min(1,(time-left['time'])/dt))
            p0=np.array(left[field],float);p1=np.array(right[field],float)
            before=keys[max(0,i-1)];after=keys[min(len(keys)-1,i+2)]
            m0=(p1-np.array(before[field]))/(right['time']-before['time'])
            m1=(np.array(after[field])-p0)/(after['time']-left['time'])
            if left.get('stop'): m0=np.zeros(3)
            if right.get('stop'): m1=np.zeros(3)
            if keys[0].get('curve')=='quintic':
                def acceleration(index):
                    if index==0 or index==len(keys)-1 or keys[index].get('stop'):return np.zeros(3)
                    a,b,c=keys[index-1:index+2]
                    v0=(np.array(b[field])-a[field])/(b['time']-a['time'])
                    v1=(np.array(c[field])-b[field])/(c['time']-b['time'])
                    return 2*(v1-v0)/(c['time']-a['time'])
                a0=acceleration(i)*dt*dt;a1=acceleration(i+1)*dt*dt
                v0=m0*dt;v1=m1*dt
                d=p1-p0-v0-a0/2;e=v1-v0-a0;f=a1-a0
                return p0+v0*u+a0*u*u/2+(10*d-4*e+f/2)*u**3+(-15*d+7*e-f)*u**4+(6*d-3*e+f/2)*u**5
            return (2*u**3-3*u*u+1)*p0+(u**3-2*u*u+u)*dt*m0+(-2*u**3+3*u*u)*p1+(u**3-u*u)*dt*m1
    return np.array(keys[-1][field],float)


def sample(flight,time):
    eye,target=(sample_track(flight['keyframes'],time,k) for k in ('eye','target'))
    follow=flight.get('follow')
    if follow and time<follow['end']:
        u=np.clip((time-follow['fade_start'])/(follow['end']-follow['fade_start']),0,1)
        weight=follow['weight']*(1-u*u*u*(10-15*u+6*u*u))
        target=target*(1-weight)+sample_track(flight['drone'],time,'position')*weight
    return eye,target


def assembly_pose(flight,time,pose):
    """Rigid world-Z turn of every computer part, independent of the drone."""
    turn=flight.get('turntable')
    if not turn or time<=turn['start']:return tuple(pose)
    u=np.clip((time-turn['start'])/(turn['end']-turn['start']),0,1)
    angle=math.radians(turn['degrees'])*u*u*u*(10-15*u+6*u*u)
    c,s=math.cos(angle),math.sin(angle)
    rotation=np.array([[c,-s,0],[s,c,0],[0,0,1.]])
    pivot=np.array(turn['pivot'])*SCALE
    position=rotation @ (np.array(pose[:3])-pivot)+pivot
    basis=rotation @ np.array(pose[3:]).reshape(3,3)
    return tuple(np.rint(position).astype(int))+tuple(np.rint(basis.flatten()).astype(int))


def steering_time(flight,time):
    settings=flight.get('steering')
    if not settings:return time
    u=np.clip((time-settings['fade_start'])/(settings['end']-settings['fade_start']),0,1)
    lead=settings['lead_seconds']*(1-u*u*u*(10-15*u+6*u*u))
    return min(flight['drone'][-1]['time'],time+lead)


def drone_scale(flight,time):
    settings=flight.get('miniature')
    if not settings:return 1.
    u=np.clip((time-settings['start'])/(settings['end']-settings['start']),0,1)
    return settings['scale']+(1-settings['scale'])*u*u*u*(10-15*u+6*u*u)


def drone_rotation(flight, time):
    """Original ship nose is +X; anticipate the upcoming path tangent."""
    keys=flight['drone'];start=keys[0]['time'];end=keys[-1]['time']
    def velocity(t):
        lo=max(start,t-.05);hi=min(end,t+.05)
        return (sample_track(keys,hi,'position')-sample_track(keys,lo,'position'))/(hi-lo)
    time=steering_time(flight,time)
    v=velocity(time);speed=np.linalg.norm(v)
    if speed<1e-6: raise ValueError('Drone track has no heading at this sample')
    forward=v/speed
    left=np.cross([0.,0.,1.],forward);left/=np.linalg.norm(left)
    up=np.cross(forward,left)
    # Bank into the anticipated turn without delaying the nose heading.
    settings=flight.get('bank',{});window=settings.get('smoothing_seconds',.24)
    limit=math.radians(settings.get('max_degrees',16));accel=settings.get('acceleration_scale',200)
    def raw_bank(t):
        lo=max(start,t-.15);hi=min(end,t+.15)
        before=velocity(lo);after=velocity(hi)
        turn=math.atan2(before[0]*after[1]-before[1]*after[0],
                        before[0]*after[0]+before[1]*after[1])/(hi-lo)
        return np.clip(-math.atan2(np.linalg.norm(velocity(t))*turn,accel),-limit,limit)
    weights=[1,2,3,4,3,2,1]
    bank=sum(w*raw_bank(float(np.clip(time+(i-3)*window/3,start,end))) for i,w in enumerate(weights))/sum(weights)
    c,s=math.cos(bank),math.sin(bank)
    roll=np.array([[1,0,0],[0,c,-s],[0,s,c]])
    return np.column_stack((forward,left,up)) @ roll


def encode_animation(poses, visibility, fov):
    """Encode complete authored tracks, including motion while off screen."""
    previous = np.zeros((len(poses[0]),12), dtype=np.int64)
    on = [False]*len(previous)
    out=bytearray()
    for frame, enabled in zip(poses,visibility):
        frame_start=len(out)
        for obj,state in enumerate(frame):
            delta=np.asarray(state,dtype=np.int64)-previous[obj]
            if any(d < -32768 or d > 32767 for d in delta[3:]):
                raise ValueError("Matrix jump exceeds signed 16-bit delta; add intermediate poses")
            flag=0 if enabled[obj]==on[obj] else (0x80 if enabled[obj] else 0x40)
            mask=0; payload=bytearray()
            for k,d in enumerate(delta[:3]):
                size=0 if d==0 else (1 if -128<=d<=127 else (2 if -32768<=d<=32767 else 4))
                mask |= {0:0,1:1,2:2,4:3}[size] << (2*k)
                payload.extend(int(d).to_bytes(size,'little',signed=True))
            size=2 if any(d < -128 or d > 127 for d in delta[3:]) else 1
            if size==2: mask |= 64
            for k,d in enumerate(delta[3:]):
                if d:
                    mask |= 128<<k
                    payload.extend(int(d).to_bytes(size,'little',signed=True))
            if mask or flag:
                length=(mask.bit_length()+7)//8
                out.extend((0xc0 | (obj>>4),flag | (length<<4) | (obj&15)))
                out.extend(mask.to_bytes(length,'little'));out.extend(payload)
            previous[obj]=state;on[obj]=enabled[obj]
        out.extend((255,round(fov*256/360)))
        if len(out)-frame_start>4096:
            raise ValueError("Animation frame exceeds the DOS streaming buffer contract")
    out.extend((255,255))
    return bytes(out)


def prepare(root, build, command, presentation=None):
    from presentation import load as load_presentation, snapshot, DEFAULT
    manifest=Path(presentation or DEFAULT).resolve()
    config,source_root,inputs=load_presentation(manifest,root)
    root=snapshot(source_root,build/'model-snapshot') if source_root!=(build/'model-snapshot').resolve() else source_root
    colors_config=json.loads(inputs['materials'].read_text())
    colors={name:(r['base'],r['rgb']) for name,r in colors_config.items()}
    browser=root/'browser'
    data=json.loads((browser/'model.json').read_text())
    output=build/'robotron';output.mkdir(parents=True,exist_ok=True)
    for old in output.glob('U2E.*'): old.unlink()
    records={p['name']:p for p in data['parts']}
    sources={}; cached={}
    # Regenerate the close-up exterior directly from the current SCAD sources.
    # Cache is local to this checkout; the canonical repository stays read-only.
    fresh=output/'source-front';fresh.mkdir(exist_ok=True)
    source_files={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in sorted(root.rglob('*.scad'))}
    source_key=hashlib.sha256(json.dumps(source_files,sort_keys=True).encode()).hexdigest()
    source_stamp=fresh/'sources.sha256'
    fresh_names=['fascia','drives','drive-insets','drive-latch-0','drive-latch-1',
                 'drive-led-0','drive-led-1','drive-direction-0','drive-direction-1',
                 'reset','power','power-housing','case-base']
    for name in fresh_names:
        path=fresh/(name+'.stl')
        if not path.exists() or not source_stamp.exists() or source_stamp.read_text()!=source_key:
            openscad(command,root/'model.scad',path,
                     ['--export-format','binstl','-D','part='+json.dumps(name)])
    source_stamp.write_text(source_key)

    def load(record):
        path=browser/record['file']
        if not path.is_file(): path=root/record['file']
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != record['sha256']: raise ValueError(f'Stale model export: {path}')
        sources[record['file']]=digest
        if record.get('name') in fresh_names:
            path=fresh/(record['name']+'.stl')
            sources[str(path.relative_to(output))]=hashlib.sha256(path.read_bytes()).hexdigest()
        if record['file'] not in cached:
            cached[record['file']]=trimesh.load_mesh(path,process=True)
        return cached[record['file']].copy()

    objects=[(label,mesh,color,'exterior') for label,mesh,color in exterior()]
    from source_geometry import front_parts
    objects.extend(front_parts(load,records))
    for override in config.get('models',[]):
        matches=[i for i,item in enumerate(objects) if item[0]==override['name']]
        if len(matches)!=1:raise ValueError(f"Unknown exterior override: {override['name']}")
        i=matches[0];label,old,color,kind=objects[i]
        stl=output/(label+'-replacement.stl')
        openscad(command,manifest.parent/override['scad'],stl,['--export-format','binstl'])
        color=override.get('material',color)
        if color not in colors:raise ValueError('Unknown replacement material')
        objects[i]=(label,trimesh.load_mesh(stl,process=True),color,kind)
    key_legends={}
    instances=[{'mesh':label,'pose':(0,0,0,*IDENTITY),'kind':kind}
               for label,mesh,color,kind in objects]
    packages={m['id']:m for m in data['pcbComponents']['models']}
    chips={'motherboard':[], 'display-controller':[]}
    chip_parts=[]
    for inst in data['pcbComponents']['instances']:
        if inst['board'] not in chips: continue
        model=packages[inst['model']]
        a=math.radians(inst['rotation']); c,s=math.cos(a),math.sin(a)
        rotation=np.array([[c,-s,0],[s,c,0],[0,0,1.]])
        if inst['side']==-1: rotation=rotation @ np.diag([1,-1,-1])
        position=np.array(inst['position'])
        m=load(model['meshes']['body'])
        m.vertices=m.vertices @ rotation.T + position
        chips[inst['board']].append(m)
        leads=load(model['meshes']['leads'])
        leads.vertices=leads.vertices @ rotation.T + position
        chip_parts.append((inst,m,leads))
    keymesh={m['name']:m for m in data['keyMeshes']}
    keys=[]
    a=math.radians(data['keyboard']['slope']);c,s=math.cos(a),math.sin(a)
    rot=np.array([[1,0,0],[0,c,-s],[0,s,c]])
    key_variants={}
    cap_geometry={}
    key_styles={}
    for key in data['keys']:
        signature=(key['mesh'],tuple(key['legend']),key['style'])
        if signature not in key_variants:
            name='key-'+str(len(key_variants))
            key_variants[signature]=name
            source=load(keymesh[key['mesh']])
            if key['mesh'] not in cap_geometry:
                pieces=[source]
                for field in ('coreMesh','insertMesh'):
                    if key.get(field):pieces.append(load(keymesh[key[field]]))
                cap_geometry[key['mesh']]=keycaps.detailed(trimesh.util.concatenate(pieces))
            cap=cap_geometry[key['mesh']]
            material={0:'black',1:'metal',2:'red'}[key['style']]
            objects.append((name,cap,material,'keycap'))
            key_styles[name]=key['style']
            key_legends[name]=keycaps.surface_legends(key['legend'],cap,SCALE)
        name=key_variants[signature]
        position=rot @ np.array([key['x'],key['y'],0])+np.array([0,data['keyboard']['y'],data['keyboard']['z']])
        pose=tuple(np.rint(position*SCALE).astype(int))+tuple(np.rint(rot.flatten()*16384).astype(int))
        instances.append({'mesh':name,'pose':pose,'kind':'keys'})
        m=load(keymesh[key['mesh']]);m.vertices=m.vertices @ rot.T+position
        keys.append(m)
    if len(objects)>254: raise ValueError('Robotron exceeds available mesh slots')
    report={'source':str(source_root),'snapshot':str(root),'presentation_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest(),'manifest_sha256':hashlib.sha256((browser/'model.json').read_bytes()).hexdigest(),
            'source_meshes':sources,
            'source_files':source_files,'objects':[],'key_legends':sum(bool(k['legend']) for k in data['keys'])}
    slots=[n for n in range(1,256) if n != 28]
    for slot,(label,mesh,color,kind) in zip(slots,objects):
        triangles=polygons(mesh)
        if kind=='keycap':
            # Six coarse faces come first; the native player selects one LOD.
            triangles=polygons(keycap(mesh,detailed=False))+triangles
        print(f'Robotron {slot:02}: {label}: {len(triangles)} polygons',flush=True)
        render_name=label
        ink=key_legends.get(label,[])
        face_colors=[colors[color][0]]*len(triangles)
        if kind=='keycap' and key_styles[label]==1:
            # The opaque DOS palette approximates the clear function-key shell
            # with a blue-grey rim around its silver insert.
            for i,face in enumerate(triangles[6:],6):
                if min(p[2] for p in face)/SCALE < mesh.bounds[1,2]-1:
                    face_colors[i]=colors['blue'][0]
        ink_color='white' if kind=='keycap' and key_styles[label]!=1 else 'black'
        face_colors += [colors[ink_color][0]]*len(ink)
        triangles+=ink
        sort_center=None
        binary=scene.encode('"'+render_name[:20]+'"',triangles,colors[color][0],16,
                            face_colors=face_colors,precomputed_orders=False,sort_center=sort_center,smooth=(label=='screen'))
        (output/f'U2E.{slot:03}').write_bytes(binary)
        report['objects'].append({'slot':slot,'name':label,'kind':kind,'polygons':len(triangles)})
    # New scene mapping: only our generated slots plus the byte-exact drone.
    slot_by_name={o['name']:o['slot'] for o in report['objects']}
    for inst in instances: inst['slot']=slot_by_name[inst['mesh']]
    instances.append({'slot':28,'kind':'drone','mesh':'drone'})
    instances.sort(key=lambda i:i['slot'])
    if len(instances)>=256: raise ValueError('Too many scene instances')
    used=[i['slot'] for i in instances]
    material=bytearray((HERE.parent/'MAIN/DATA/U2E.00M').read_bytes())
    offset=struct.unpack_from('<I',material,4)[0]
    material=material[:offset]+struct.pack(f'<{len(used)+1}H',len(used)+1,*used)
    for ramp in colors_config.values():
        base=ramp['base'];rgb=ramp['rgb'];color=tuple(int(rgb[i:i+2],16) for i in (1,3,5))
        for j in range(16):
            for k,v in enumerate(color):
                material[16+(base+j)*3+k]=round(v/255*63*(ramp['ambient']+ramp['diffuse']*j/15))
    # Disable city-specific colouring/sorting names; normal renderer remains.
    material[15]=ord('T')
    (output/'U2E.00M').write_bytes(material)
    flight=json.loads(inputs['flight'].read_text())
    drone=scene.decode((HERE.parent/'MAIN/DATA/U2E.028').read_bytes())
    center=np.array([(a+b)/2 for a,b in drone['bounds']])
    bounds={label:(m.bounds.mean(axis=0),float(np.linalg.norm(m.extents)/2))
            for label,m,_,_ in objects}
    poses=[];visibility=[]
    for f in range(flight['frames']):
        t=f/flight['fps'];eye,target=sample(flight,t)
        drone_pos=sample_track(flight['drone'],t,'position')
        rotation=drone_rotation(flight,t)
        rotation*=SCALE/96*drone_scale(flight,t)  # Miniature in the key channel; original scale after climbing out.
        drone_state=tuple(np.rint(drone_pos*SCALE-rotation@center).astype(int))+tuple(
            np.rint(rotation.flatten()*16384).astype(int))
        frame=[camera(eye,target)]; enabled=[True]
        for inst in instances:
            slot=inst['slot']
            pose=list(drone_state if slot==28 else assembly_pose(flight,t,inst['pose']))
            frame.append(pose)
            enabled.append(not (slot==28 and t>48.1))
        # Conservative sphere/frustum culling, rebuilt for this camera. A wide
        # vertical margin avoids coupling this bake to VGA aspect corrections.
        cam=np.array(frame[0][3:]).reshape(3,3)/16384
        tangent=math.tan(math.radians(flight['fov']/2+5))
        for i,inst in enumerate(instances,1):
            if inst['kind']=='drone' or not enabled[i]: continue
            local,radius=bounds[inst['mesh']]
            pose=frame[i]; rotation=np.array(pose[3:]).reshape(3,3)/16384
            world=rotation @ local+np.array(pose[:3])/SCALE
            x,y,z=cam @ (world-eye)
            margin=radius*math.sqrt(1+tangent*tangent)+2
            enabled[i]=bool(z+radius>512/SCALE and abs(x)<z*tangent+margin and abs(y)<z*tangent+margin)
        poses.append(frame);visibility.append(enabled)
    stream=encode_animation(poses,visibility,flight['fov'])
    (output/'U2E.0AB').write_bytes(stream)
    report['flight']=flight; report['animation_bytes']=len(stream)
    report['instances']=len(instances)
    report['drone_sha256']=hashlib.sha256((HERE.parent/'MAIN/DATA/U2E.028').read_bytes()).hexdigest()
    # Each technical page selects its own geometry and camera, including
    # component-sized crops of the detailed source boards.
    from credit_views import render_cards
    credits=render_cards(inputs['credits'],output,records,
                         load,chip_parts,keys,command)
    project=output/'credits.json'
    project.write_text(json.dumps({'version':1,'credits':credits},indent=2)+'\n')
    from music import write_credit_schedule
    write_credit_schedule(HERE.parent/'MAIN/MUSIC0.S3M',output,config['transition'],len(credits))
    end=(flight['frames']-1)*2
    (output/'U2E.PRS').write_text(f"{end-round(config['transition']['flight_fade_seconds']*70)} {end}\n")
    report['exterior_lod']='RT1715/robotron_lod.py panels; keycaps.py source-sampled skirts, shoulders and dishes'
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return project


def install(build,dos):
    import shutil
    for path in [*(build/'robotron').glob('U2E.*'),*(build/'robotron').glob('CRED.C*'),build/'robotron/CRED.TIM']:
        shutil.copyfile(path,dos/path.name)
