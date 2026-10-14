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
import fast_simplification
import scene
from prepare import openscad

HERE = Path(__file__).resolve().parent
SCALE = 64  # DOS near plane 512 becomes 8 mm; limits 16-bit projected-coordinate overflow.
IDENTITY = (16384,0,0,0,16384,0,0,0,16384)
# Keep the original drone's palette entries 0..31 and 160..251 untouched.
COLORS = {'dark':(32,'#343b3c'), 'paint':(48,'#b6ae93'), 'pcb':(64,'#38745b'),
          'metal':(80,'#bbc2c2'), 'brown':(96,'#9e793b'), 'red':(112,'#b64139'),
          'blue':(128,'#91aeb6'), 'white':(144,'#dddccb')}
# Separate objects preserve painter ordering and allow covers to close at reveal.
PARTS = [
 ('base', 'case-base', 90, 'paint', 'solid-shell'),
 ('lid', 'case-lid', 100, 'paint', 'cover'),
 ('fascia', 'fascia', 150, 'paint', 'fixed'),
 ('drives', 'drives drive-insets drive-latch-0 drive-latch-1', 200, 'dark', 'fixed'),
 ('stand', 'pedestal ring', 80, 'paint', 'fixed'),
 ('monitor', 'monitor-shell-lower monitor-shell-upper', 180, 'paint', 'fixed'),
 ('bezel', 'bezel crt-rim', 100, 'dark', 'fixed'),
 ('screen', 'crt-glass', 80, 'pcb', 'fixed'),
 ('keyboard', 'keyboard-shell keyboard-bottom', 120, 'blue', 'keyboard-cover'),
 ('deck', 'keyboard-deck', 100, 'dark', 'keyboard-cover'),
 ('keyboard-pcb', 'keyboard-pcb', 48, 'pcb', 'fixed'),
 ('controller', 'keyboard-controller-board', 24, 'pcb', 'fixed'),
 ('controller-chips', 'keyboard-controller-chips keyboard-controller-ceramic', 120, 'dark', 'fixed'),
 ('drive-frames', 'drive-frames drive-bracket', 150, 'metal', 'solid-shell'),
 ('drive-mechanisms', 'drive-mechanisms drive-head-0 drive-head-1', 160, 'metal', 'fixed'),
 ('drive-motors', 'drive-motors drive-spindle-0 drive-spindle-1', 100, 'dark', 'fixed'),
 ('drive-boards', 'drive-boards drive-adapter-boards', 64, 'pcb', 'fixed'),
 ('psu', 'psu-cover psu-chassis', 100, 'metal', 'fixed'),
 ('fan-frame', 'fan-frame fan-retainers', 80, 'metal', 'fixed'),
 ('fan', 'fan-rotor', 80, 'dark', 'fixed'),
 ('motherboard', 'logic-boards-motherboard', 40, 'pcb', 'fixed'),
 ('display-board', 'logic-boards-display-controller', 40, 'pcb', 'display'),
 ('ribbons', 'ribbon-cables drive-cable-plugs', 90, 'white', 'fixed'),
 ('controls', 'power reset', 40, 'white', 'fixed'),
 ('rear', 'rear-panel rear-socket-bodies', 90, 'paint', 'fixed'),
 ('wiring', 'power-wires-red power-wires-yellow power-wires-black cable', 80, 'brown', 'fixed'),
]


def simplify(mesh, faces):
    if len(mesh.faces) <= faces: return mesh
    def reduce(m, count):
        if len(m.faces)<=count: return m
        center=m.bounds.mean(axis=0); extent=max(m.extents)
        v,f = fast_simplification.simplify((np.asarray(m.vertices)-center)/extent, np.asarray(m.faces),
                                          target_count=count, agg=7)
        return trimesh.Trimesh(v*extent+center,f,process=True)
    reduced=reduce(mesh,faces)
    if len(reduced.faces) <= faces: return reduced
    # Vent holes and PCB drilling impose a topological floor on decimation.
    # Keep the largest connected solids, close their small openings with convex
    # envelopes, then reduce those. Full detail remains in the source and cards.
    pieces=sorted(mesh.split(only_watertight=False),key=lambda m:m.area,reverse=True)
    pieces=pieces[:max(1,faces//12)]
    hulls=[]
    for piece in pieces:
        if len(piece.vertices)<4: continue
        hull=piece.convex_hull
        budget=max(4,faces//len(pieces))
        reduced=reduce(hull,budget)
        if len(reduced.faces)>budget:
            # Bound the convex hull face count by selecting at most F/2+2
            # farthest-spaced source vertices (Euler's convex polyhedron bound).
            v=np.asarray(hull.vertices);chosen=[0]
            distances=np.full(len(v),np.inf)
            for _ in range(min(len(v),budget//2+2)-1):
                distances=np.minimum(distances, np.sum((v-v[chosen[-1]])**2,axis=1))
                chosen.append(int(np.argmax(distances)))
            reduced=trimesh.convex.convex_hull(v[chosen])
        hulls.append(reduced)
    return trimesh.util.concatenate(hulls)


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


def sample(flight, time):
    keys=flight['keyframes']
    for left,right in zip(keys,keys[1:]):
        if time <= right['time']:
            u=max(0,min(1,(time-left['time'])/(right['time']-left['time'])))
            u=u*u*(3-2*u)
            return tuple((1-u)*np.array(left[k],float)+u*np.array(right[k],float) for k in ('eye','target'))
    return tuple(np.array(keys[-1][k],float) for k in ('eye','target'))


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

    objects=[]; instances=[]
    for label,names,budget,color,kind in PARTS:
        meshes=[load(records[n]) for n in names.split()]
        # Simplify separately so small disconnected parts are not erased by a
        # large adjacent shell's error budget.
        # Leave conventional-memory headroom for 242 placed instances and
        # the animation stream; budgets count source triangles before merging.
        pieces=[simplify(m,max(12,round(budget*.55)//len(meshes))) for m in meshes]
        objects.append((label,trimesh.util.concatenate(pieces),color,kind))
        instances.append({'mesh':label,'pose':(0,0,0,*IDENTITY),'kind':kind})
    packages={m['id']:m for m in data['pcbComponents']['models']}
    chips={'motherboard':[], 'display-controller':[]}
    for name,model in packages.items():
        objects.append((name,simplify(load(model['meshes']['body']),12),'dark','package'))
    for inst in data['pcbComponents']['instances']:
        if inst['board'] not in chips: continue
        model=packages[inst['model']]
        a=math.radians(inst['rotation']); c,s=math.cos(a),math.sin(a)
        rotation=np.array([[c,-s,0],[s,c,0],[0,0,1.]])
        if inst['side']==-1: rotation=rotation @ np.diag([1,-1,-1])
        position=np.array(inst['position'])
        pose=tuple(np.rint(position*SCALE).astype(int))+tuple(np.rint(rotation.flatten()*16384).astype(int))
        instances.append({'mesh':inst['model'],'pose':pose,
                          'kind':'display' if inst['board']=='display-controller' else 'fixed'})
        m=load(model['meshes']['body'])
        m.vertices=m.vertices @ rotation.T + position
        chips[inst['board']].append(m)
    keymesh={m['name']:m for m in data['keyMeshes']}
    keys=[]
    a=math.radians(data['keyboard']['slope']);c,s=math.cos(a),math.sin(a)
    rot=np.array([[1,0,0],[0,c,-s],[0,s,c]])
    for name in sorted(set(k['mesh'] for k in data['keys'])):
        objects.append((name,simplify(load(keymesh[name]),20),'white','keycap'))
    for key in data['keys']:
        position=rot @ np.array([key['x'],key['y'],0])+np.array([0,data['keyboard']['y'],data['keyboard']['z']])
        pose=tuple(np.rint(position*SCALE).astype(int))+tuple(np.rint(rot.flatten()*16384).astype(int))
        instances.append({'mesh':key['mesh'],'pose':pose,'kind':'keys'})
        m=load(keymesh[key['mesh']]);m.vertices=m.vertices @ rot.T+position
        keys.append(m)
    if len(objects)>41: raise ValueError('Robotron exceeds 41 non-drone mesh slots')
    report={'source':str(root),'manifest_sha256':hashlib.sha256((browser/'model.json').read_bytes()).hexdigest(),
            'source_meshes':sources,'objects':[]}
    slots=[n for n in range(1,43) if n != 28]
    for slot,(label,mesh,color,kind) in zip(slots,objects):
        triangles=polygons(mesh)
        print(f'Robotron {slot:02}: {label}: {len(triangles)} polygons',flush=True)
        render_name=('_' if 'board' in label or label in ('keyboard-pcb','controller','keyboard','deck','base','lid','fascia') else '')+label
        binary=scene.encode('"'+render_name[:20]+'"',triangles,COLORS[color][0],16)
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
        forward=target-eye;distance=np.linalg.norm(forward);forward/=distance
        # A small escort just ahead/below the lens; it leads into the reveal.
        drone_pos=eye+forward*min(40,distance*.58)+np.array([0,0,-3])
        if t>=44:
            e0,t0=sample(flight,44)
            lead=t0-e0; lead/=np.linalg.norm(lead)
            start=e0+lead*40+np.array([0,0,-3])
            u=min(1,(t-44)/4);u=u*u*(3-2*u)
            drone_pos=(1-u)*start+u*np.array([60,-185,160])
        yaw=math.atan2(forward[1],forward[0])+math.pi/2
        c,s=math.cos(yaw),math.sin(yaw)
        rotation=np.array([[c,-s,0],[s,c,0],[0,0,1.]])
        rotation*=SCALE/128  # Preserve the escort size while scaling the world.
        drone_state=tuple(np.rint(drone_pos*SCALE-rotation@center).astype(int))+tuple(
            np.rint(rotation.flatten()*16384).astype(int))
        frame=[camera(eye,target)]; enabled=[True]
        for inst in instances:
            slot=inst['slot'];kind=inst['kind']
            z=0
            if kind=='cover': z=max(0,1-(t-42)/5)*180
            if kind=='keyboard-cover': z=max(0,1-(t-33)/4)*100
            pose=list(drone_state if slot==28 else inst['pose'])
            pose[2]+=round(z*SCALE)
            frame.append(pose)
            enabled.append(not ((kind=='cover' and t<42) or
                                (kind=='keyboard-cover' and t<33) or
                                (kind=='keys' and t<34) or (kind=='display' and t<11) or (kind=='solid-shell' and t<42)))
        exterior={'base','lid','fascia','drives','stand','monitor','bezel','screen',
                  'keyboard','deck','controls','rear','wiring'}
        for i,inst in enumerate(instances,1):
            # The legacy painter sorts whole objects. Remove enclosed contents
            # once the lids close, otherwise their centres can sort in front.
            if t>=47 and inst['mesh'] not in exterior and inst['kind'] not in ('keys','drone'):
                enabled[i]=False
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
    (output/'report.json').write_text(json.dumps(report,indent=2)+'\n')
    # Detailed credits use canonical exported parts, not the reduced DOS meshes.
    cards=[
      ('processor', ['logic-boards-motherboard'], ['U880 / Z80','8-bit CPU','Robotron 1715M - 256 KB RAM'], 'motherboard'),
      ('drives', ['drive-frames','drive-mechanisms','drive-boards','drives'], ['Twin floppy drives','5.25-inch removable media','Robotron / TEAC mechanisms'], None),
      ('keyboard', ['keyboard-pcb','keyboard-controller-board','keyboard-controller-chips','keyboard-controller-ceramic'], ['Keyboard electronics','UB880D controller','Separate controller and contact PCB'], None),
      ('display', ['logic-boards-display-controller'], ['Display controller','SAB8275P','Three UL6516D memories'], 'display-controller'),
      ('monitor', ['bezel','crt-rim','crt-glass','monitor-shell-lower','monitor-shell-upper','pedestal'], ['CRT monitor','Monochrome display','Separate monitor and stand'], None),
      ('psu', ['psu-chassis','psu-cover','fan-frame','fan-rotor','fan-retainers'], ['Power supply','Shielded PSU assembly','Fan-cooled system unit'], None),
      ('robotron', ['case-base','case-lid','fascia','drives','monitor-shell-lower','monitor-shell-upper','bezel','crt-glass','pedestal','keyboard-shell','keyboard-deck'], ['Robotron 1715M','A journey inside the machine','Models: Danila / 3d-models'], 'keys')]
    credits=[]
    for name,names,lines,extras in cards:
        script=[]
        for n in names:
            p=records[n];rgb=p.get('color','#999999')
            script.append(f'color("{rgb}") import({json.dumps(str(browser/p["file"]))});')
        if extras in chips:
            for i,m in enumerate(chips[extras]):
                path=output/f'credit-{extras}-{i}.stl';m.export(path)
                script.append(f'color("#303333") import({json.dumps(str(path))});')
        if extras=='keys':
            path=output/'credit-keys.stl';trimesh.util.concatenate(keys).export(path)
            script.append(f'color("#dddccb") import({json.dumps(str(path))});')
        scad=output/f'{name}.scad';scad.write_text('\n'.join(script)+'\n')
        png=output/f'{name}.png'
        openscad(command,scad,png,['--render','--imgsize','960,600','--viewall','--autocenter'])
        credits.append({'image':str(png),'lines':lines,'hold_frames':230})
    project=output/'credits.json'
    project.write_text(json.dumps({'version':1,'credits':credits},indent=2)+'\n')
    return project


def install(build,dos):
    import shutil
    for path in (build/'robotron').glob('U2E.*'):
        shutil.copyfile(path,dos/path.name)
