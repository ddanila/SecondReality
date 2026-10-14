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
import legends
from robotron_lod import exterior, keycap
from PIL import Image, ImageOps
from prepare import openscad

HERE = Path(__file__).resolve().parent
SCALE = 64  # DOS near plane 512 becomes 8 mm; limits 16-bit projected-coordinate overflow.
IDENTITY = (16384,0,0,0,16384,0,0,0,16384)
# Keep the original drone's palette entries 0..31 and 160..251 untouched.
COLORS = {'dark':(32,'#343b3c'), 'paint':(48,'#b6ae93'), 'pcb':(64,'#38745b'),
          'metal':(80,'#bbc2c2'), 'black':(96,'#080a0a'), 'red':(112,'#b64139'),
          'blue':(128,'#91aeb6'), 'white':(144,'#dddccb')}

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
    """Time-aware cubic Hermite track: continuous speed across scenic waypoints."""
    for i,(left,right) in enumerate(zip(keys,keys[1:])):
        if time <= right['time']:
            dt=right['time']-left['time']
            u=max(0,min(1,(time-left['time'])/dt))
            p0=np.array(left[field],float);p1=np.array(right[field],float)
            before=keys[max(0,i-1)];after=keys[min(len(keys)-1,i+2)]
            m0=(p1-np.array(before[field]))/(right['time']-before['time'])
            m1=(np.array(after[field])-p0)/(after['time']-left['time'])
            return (2*u**3-3*u*u+1)*p0+(u**3-2*u*u+u)*dt*m0+(-2*u**3+3*u*u)*p1+(u**3-u*u)*dt*m1
    return np.array(keys[-1][field],float)


def sample(flight,time):
    return tuple(sample_track(flight['keyframes'],time,k) for k in ('eye','target'))


def drone_rotation(flight, time):
    """Original ship nose is local +X; align it with the 3D path tangent."""
    keys=flight['drone'];start=keys[0]['time'];end=keys[-1]['time']
    def velocity(t):
        lo=max(start,t-.05);hi=min(end,t+.05)
        return (sample_track(keys,hi,'position')-sample_track(keys,lo,'position'))/(hi-lo)
    v=velocity(time);speed=np.linalg.norm(v)
    if speed<1e-6: raise ValueError('Drone track has no heading at this sample')
    forward=v/speed
    left=np.cross([0.,0.,1.],forward);left/=np.linalg.norm(left)
    up=np.cross(forward,left)
    # Bank into the turn, instead of an unrelated periodic rocking motion.
    lo=max(start,time-.15);hi=min(end,time+.15)
    before=velocity(lo);after=velocity(hi)
    turn=math.atan2(before[0]*after[1]-before[1]*after[0],
                    before[0]*after[0]+before[1]*after[1])/(hi-lo)
    bank=np.clip(-math.atan2(speed*turn,180.),-math.radians(20),math.radians(20))
    c,s=math.cos(bank),math.sin(bank)
    roll=np.array([[1,0,0],[0,c,-s],[0,s,c]])
    return np.column_stack((forward,left,up)) @ roll


def encode_animation(poses, visibility, fov):
    """Encode complete authored tracks, including motion while off screen."""
    previous = np.zeros((len(poses[0]),12), dtype=np.int64)
    on = [False]*len(previous)
    out=bytearray()
    for frame, enabled in zip(poses,visibility):
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
    out.extend((255,255))
    return bytes(out)


def prepare(root, build, command):
    root=Path(root).resolve(); browser=root/'browser'
    data=json.loads((browser/'model.json').read_text())
    output=build/'robotron';output.mkdir(parents=True,exist_ok=True)
    for old in output.glob('U2E.*'): old.unlink()
    records={p['name']:p for p in data['parts']}
    sources={}; cached={}

    def load(record):
        path=browser/record['file']
        if not path.is_file(): path=root/record['file']
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != record['sha256']: raise ValueError(f'Stale model export: {path}')
        sources[record['file']]=digest
        if record['file'] not in cached:
            cached[record['file']]=trimesh.load_mesh(path,process=True)
        return cached[record['file']].copy()

    objects=[(label,mesh,color,'exterior') for label,mesh,color in exterior()]
    key_legends={}
    instances=[{'mesh':label,'pose':(0,0,0,*IDENTITY),'kind':kind}
               for label,mesh,color,kind in objects]
    packages={m['id']:m for m in data['pcbComponents']['models']}
    chips={'motherboard':[], 'display-controller':[]}
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
    keymesh={m['name']:m for m in data['keyMeshes']}
    keys=[]
    a=math.radians(data['keyboard']['slope']);c,s=math.cos(a),math.sin(a)
    rot=np.array([[1,0,0],[0,c,-s],[0,s,c]])
    key_variants={}
    for key in data['keys']:
        signature=(key['mesh'],tuple(key['legend']),key['style'])
        if signature not in key_variants:
            name='key-'+str(len(key_variants))
            key_variants[signature]=name
            source=load(keymesh[key['mesh']])
            objects.append((name,keycap(source),'blue' if key['style'] else 'white','keycap'))
            key_legends[name]=legends.polygons(key['legend'],source.bounds,SCALE)
        name=key_variants[signature]
        position=rot @ np.array([key['x'],key['y'],0])+np.array([0,data['keyboard']['y'],data['keyboard']['z']])
        pose=tuple(np.rint(position*SCALE).astype(int))+tuple(np.rint(rot.flatten()*16384).astype(int))
        instances.append({'mesh':name,'pose':pose,'kind':'keys'})
        m=load(keymesh[key['mesh']]);m.vertices=m.vertices @ rot.T+position
        keys.append(m)
    if len(objects)>254: raise ValueError('Robotron exceeds available mesh slots')
    report={'source':str(root),'manifest_sha256':hashlib.sha256((browser/'model.json').read_bytes()).hexdigest(),
            'source_meshes':sources,'objects':[],'key_legends':sum(bool(k['legend']) for k in data['keys'])}
    slots=[n for n in range(1,256) if n != 28]
    for slot,(label,mesh,color,kind) in zip(slots,objects):
        triangles=polygons(mesh)
        print(f'Robotron {slot:02}: {label}: {len(triangles)} polygons',flush=True)
        render_name=('_' if label in ('keyboard','deck') else '')+label
        ink=key_legends.get(label,[])
        colors=[COLORS[color][0]]*len(triangles)+[COLORS['black'][0]]*len(ink)
        triangles+=ink
        sort_center=None
        if label.startswith('drive-'):
            # Use one X/Z sorting anchor per drive, with each layer's own Y.
            # A corner LED must sort in front of the drive skin even when its
            # geometric centre is farther away in an oblique camera view.
            index=int(label.rsplit('-',1)[1])
            sort_center=(round((-158+154*index)*SCALE),
                         round(mesh.bounds.mean(axis=0)[1]*SCALE),81*SCALE)
        binary=scene.encode('"'+render_name[:20]+'"',triangles,COLORS[color][0],16,
                            face_colors=colors,precomputed_orders=False,sort_center=sort_center)
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
    for base,rgb in COLORS.values():
        color=tuple(int(rgb[i:i+2],16) for i in (1,3,5))
        for j in range(16):
            for k,v in enumerate(color):
                material[16+(base+j)*3+k]=round(v/255*63*(0.25+0.75*j/15))
    # Disable city-specific colouring/sorting names; normal renderer remains.
    material[15]=ord('T')
    (output/'U2E.00M').write_bytes(material)
    flight=json.loads((HERE/'assets/robotron/flight.json').read_text())
    drone=scene.decode((HERE.parent/'MAIN/DATA/U2E.028').read_bytes())
    center=np.array([(a+b)/2 for a,b in drone['bounds']])
    bounds={label:(m.bounds.mean(axis=0),float(np.linalg.norm(m.extents)/2))
            for label,m,_,_ in objects}
    poses=[];visibility=[]
    for f in range(flight['frames']):
        t=f/flight['fps'];eye,target=sample(flight,t)
        drone_pos=sample_track(flight['drone'],t,'position')
        rotation=drone_rotation(flight,t)
        rotation*=SCALE/96  # Approximately 7.5 mm wide in the assembly's units.
        drone_state=tuple(np.rint(drone_pos*SCALE-rotation@center).astype(int))+tuple(
            np.rint(rotation.flatten()*16384).astype(int))
        frame=[camera(eye,target)]; enabled=[True]
        for inst in instances:
            slot=inst['slot']
            pose=list(drone_state if slot==28 else inst['pose'])
            frame.append(pose)
            enabled.append(True)
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
    # Detailed credits use canonical exported parts, not the reduced DOS meshes.
    cards=[
      ('processor', ['logic-boards-motherboard'], ['U880 / Z80','8-bit CPU','Robotron 1715M - 256 KB RAM'], 'motherboard'),
      ('drives', ['drive-frames','drive-mechanisms','drive-boards','drives'], ['Twin floppy drives','5.25-inch removable media','Robotron / TEAC mechanisms'], None),
      ('keyboard', ['keyboard-controller-board','keyboard-controller-chips','keyboard-controller-ceramic'], ['Keyboard electronics','UB880D controller','Keyboard controller board'], None),
      ('display', ['logic-boards-display-controller'], ['Display controller','SAB8275P','Three UL6516D memories'], 'display-controller'),
      ('monitor', ['bezel','crt-rim','crt-glass','monitor-shell-lower','monitor-shell-upper','pedestal'], ['CRT monitor','Monochrome display','Separate monitor and stand'], None),
      ('psu', ['psu-chassis','psu-cover','fan-frame','fan-rotor','fan-retainers'], ['Power supply','Shielded PSU assembly','Fan-cooled system unit'], None),
      ('robotron', ['case-base','case-lid','fascia','drives','monitor-shell-lower','monitor-shell-upper','bezel','crt-glass','pedestal','keyboard-shell','keyboard-deck'], ['Robotron 1715M','A journey inside the machine'], 'keys')]
    credits=[]
    for name,names,lines,extras in cards:
        if name=='keyboard':
            names=[n for n in records if n.startswith('keyboard-controller-')]
        if extras in chips:
            names=[n for n in records if n.startswith('logic-') and n.endswith('-'+extras)]
        script=[]
        for n in names:
            p=records[n];load(p)  # Validate every source used by the photograph.
            rgb=p.get('color','#999999')
            script.append(f'color("{rgb}") import({json.dumps(str(browser/p["file"]))});')
        if extras in chips:
            for i,m in enumerate(chips[extras]):
                path=output/f'credit-{extras}-{i}.stl';m.export(path)
                script.append(f'color("#303333") import({json.dumps(str(path))});')
        if extras=='keys':
            path=output/'credit-keys.stl';trimesh.util.concatenate(keys).export(path)
            script.append(f'color("#dddccb") import({json.dumps(str(path))});')
        if name=='display': script=['rotate([180,0,0]) {',*script,'}']
        scad=output/f'{name}.scad';scad.write_text('\n'.join(script)+'\n')
        png=output/f'{name}.png'
        openscad(command,scad,png,['--render','--colorscheme','Tomorrow Night','--imgsize','960,600','--viewall','--autocenter'])
        # Replace only the known renderer background, then letterbox the image
        # to the DOS card aspect ratio and draw a one-pixel VGA white frame.
        im=Image.open(png).convert('RGB')
        pixels=np.array(im); background=np.array([29,31,33])
        pixels[np.all(pixels==background,axis=2)]=0
        im=Image.fromarray(pixels)
        im=ImageOps.contain(im,(948,588))
        canvas=Image.new('RGB',(960,600),'black')
        canvas.paste(im,((960-im.width)//2,(600-im.height)//2))
        ImageOps.expand(canvas,border=6,fill='white').resize((960,600)).save(png)
        credits.append({'image':str(png),'lines':lines,'hold_frames':230})
    project=output/'credits.json'
    project.write_text(json.dumps({'version':1,'credits':credits},indent=2)+'\n')
    report['exterior_lod']='RT1715/robotron_lod.py (authored panels; source-dimension keycaps)'
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    return project


def install(build,dos):
    import shutil
    for path in (build/'robotron').glob('U2E.*'):
        shutil.copyfile(path,dos/path.name)
