"""Load source meshes for a credit-only render; no flyover or guest build."""
import hashlib,json,math
from pathlib import Path
import numpy as np
import trimesh
from prepare import openscad


def load_scene(root,output,command):
    root=Path(root);output=Path(output);browser=root/'browser'
    data=json.loads((browser/'model.json').read_text());records={p['name']:p for p in data['parts']}
    cached={};fresh=output/'source-front';fresh.mkdir(parents=True,exist_ok=True)
    sources={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*.scad'))}
    key=hashlib.sha256(json.dumps(sources,sort_keys=True).encode()).hexdigest()
    fronts={'fascia','drives','drive-insets','drive-latch-0','drive-latch-1','case-base'}
    def load(record):
        name=record.get('name');path=browser/record['file']
        if not path.exists():path=root/record['file']
        if path not in cached:
            if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:
                raise ValueError('Stale source mesh: '+str(path))
            selected=path
            if name in fronts:
                selected=fresh/(name+'.stl');stamp=fresh/(name+'.sha256')
                if not selected.exists() or not stamp.exists() or stamp.read_text()!=key:
                    openscad(command,root/'model.scad',selected,['--export-format','binstl','-D','part='+json.dumps(name)])
                    stamp.write_text(key)
            cached[path]=trimesh.load_mesh(selected,process=True)
        return cached[path].copy()
    packages={m['id']:m for m in data['pcbComponents']['models']};chips=[]
    for inst in data['pcbComponents']['instances']:
        if inst['board'] not in ('motherboard','display-controller'):continue
        a=math.radians(inst['rotation']);c,s=math.cos(a),math.sin(a)
        rotation=np.array([[c,-s,0],[s,c,0],[0,0,1.]])
        if inst['side']==-1:rotation=rotation @ np.diag([1,-1,-1])
        parts=[]
        for kind in ['body','leads']:
            mesh=load(packages[inst['model']]['meshes'][kind]);mesh.vertices=mesh.vertices @ rotation.T+np.array(inst['position']);parts.append(mesh)
        chips.append((inst,*parts))
    meshes={m['name']:m for m in data['keyMeshes']};keys=[]
    a=math.radians(data['keyboard']['slope']);c,s=math.cos(a),math.sin(a)
    rotation=np.array([[1,0,0],[0,c,-s],[0,s,c]])
    for keycap in data['keys']:
        position=rotation @ np.array([keycap['x'],keycap['y'],0])+np.array([0,data['keyboard']['y'],data['keyboard']['z']])
        mesh=load(meshes[keycap['mesh']]);mesh.vertices=mesh.vertices @ rotation.T+position;keys.append(mesh)
    return records,load,chips,keys
