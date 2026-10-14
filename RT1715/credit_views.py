"""Detailed, individually framed technical photographs from current meshes."""
import json
from pathlib import Path
import numpy as np
import trimesh
from PIL import Image, ImageOps
from prepare import openscad


def render_cards(config, output, records, load, chips, keys, command):
    cards=json.loads(config.read_text()); result=[]; report=[]
    for card in cards:
        name=card['image']; view=card['view']; names=[]
        for prefix in view['parts']:
            matches=[n for n in records if n==prefix or n.startswith(prefix+'-')]
            if not matches: raise ValueError(f'No parts match {prefix}')
            names.extend(matches)
        board=view.get('board')
        if board:
            names.extend(n for n in records if n.startswith('logic-') and n.endswith('-'+board))
        names=list(dict.fromkeys(names))
        solids=[(n,load(records[n]),records[n].get('color','#999999')) for n in names]
        board=view.get('board')
        selected=[]
        for instance,m,leads in chips:
            if instance['board']==board:
                highlight=any(label in instance['label'] for label in view.get('highlight_chips',[]))
                solids.append((instance['id'],m,'#c6a66a' if highlight else '#303333'))
                solids.append((instance['id']+'-pins',leads,'#a6aaa5'))
                if any(label in instance['label'] for label in view.get('focus_chips',[])):
                    selected.append(m)
        if view.get('keys'):
            solids.append(('keys',trimesh.util.concatenate(keys),'#dddccb'))
        if view.get('focus_parts'):
            selected.extend(m for n,m,color in solids if n in view['focus_parts'])
        if view.get('focus_component'):
            component=next(m for n,m,color in solids if n==view['focus_component'])
            pieces=component.split(only_watertight=False)
            largest=max(len(m.faces) for m in pieces)
            pieces=[m for m in pieces if len(m.faces)>=largest*.5]
            selected.append(min(pieces,key=lambda m:m.bounds.mean(axis=0)[0]))
        crop=None
        if view.get('focus_chips') or view.get('focus_parts') or view.get('focus_component'):
            if not selected: raise ValueError(f'Empty component focus: {name}')
            bounds=trimesh.util.concatenate(selected).bounds
            margin=np.array(view.get('margin',[10,10,8]))
            crop=[(bounds[0]-margin).tolist(),(bounds[1]+margin).tolist()]
        script=[]
        for i,(label,m,color) in enumerate(solids):
            path=output/f'{name}-{i}.stl';m.export(path)
            shape=f'import({json.dumps(str(path))});'
            if crop:
                lo,hi=np.array(crop[0]),np.array(crop[1])
                shape='intersection() { '+shape+' translate('+json.dumps(lo.tolist())+') cube('+json.dumps((hi-lo).tolist())+'); }'
            script.append(f'color("{color}") {{ {shape} }}')
        if view.get('flip'): script=['rotate([180,0,0]) {',*script,'}']
        scad=output/f'{name}.scad';scad.write_text('\n'.join(script)+'\n')
        png=output/f'{name}.png'
        angle=view.get('angle',[55,0,35])
        camera=','.join(str(v) for v in [0,0,0,*angle,0])
        openscad(command,scad,png,['--render','--colorscheme','Tomorrow Night',
                 '--imgsize','960,600','--camera',camera,'--viewall','--autocenter'])
        pixels=np.array(Image.open(png).convert('RGB'))
        pixels[np.all(pixels==[29,31,33],axis=2)]=0
        im=ImageOps.contain(Image.fromarray(pixels),(948,588))
        canvas=Image.new('RGB',(960,600),'black')
        canvas.paste(im,((960-im.width)//2,(600-im.height)//2))
        ImageOps.expand(canvas,border=6,fill='white').resize((960,600)).save(png)
        result.append(dict(image=str(png),lines=card['lines'],hold_frames=200))
        report.append(dict(image=name,parts=names,focus_chips=view.get('focus_chips'),crop=crop,angle=angle))
    (output/'credit-views.json').write_text(json.dumps(report,indent=2)+'\n')
    return result
