"""Host-rendered exploded system-unit view, using the installed source geometry."""
import hashlib,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from prepare import openscad

PREFIXES=('case-base','case-lid','fascia','drives','drive-insets','drive-latch',
          'drive-frames','drive-mechanisms','drive-boards','psu-chassis','psu-cover',
          'logic-boards','logic-mounts','logic-connectors')
CAMERA='0,0,65,40,0,25,1050'


def render(output,records,load,chips,command):
    output=Path(output);folder=output/'cutaway';folder.mkdir(exist_ok=True)
    solids=[]
    for name,record in records.items():
        if any(name==p or name.startswith(p+'-') for p in PREFIXES):
            solids.append((name,load(record),record.get('color','#999999')))
    for inst,mesh,leads in chips:
        solids.extend([(inst['id']+'-'+inst['board'],mesh,'#303333'),
                       (inst['id']+'-pins-'+inst['board'],leads,'#a6aaa5')])
    digest=hashlib.sha256(Path(__file__).read_bytes())
    for name,mesh,color in solids:digest.update(name.encode()+color.encode()+mesh.vertices.tobytes()+mesh.faces.tobytes())
    signature=digest.hexdigest();stamp=folder/'signature.txt'
    if stamp.exists() and stamp.read_text()==signature and all((folder/f'{n:02}.png').exists() for n in range(16)):return
    for i,(_,mesh,_) in enumerate(solids):mesh.export(folder/f'part-{i}.stl')
    def group(name):
        if name.endswith('display-controller'):return 'VIDEO'
        if name.endswith('motherboard'):return 'CPU'
        if name.startswith('psu'):return 'PSU'
        if name.startswith('drive'):return 'DRIVES'
        return None
    def script(t,mask=False):
        u=min(1,t/.65);u=u*u*(3-2*u)
        v=max(0,(t-.4)/.6);v=v*v*(3-2*v)
        lines=[]
        for i,(name,mesh,color) in enumerate(solids):
            z=600*u if name=='case-lid' else 65*v if name.endswith('display-controller') else 0
            if mask:color={'CPU':'#ff0000','VIDEO':'#00ff00','DRIVES':'#0000ff','PSU':'#ff00ff'}.get(group(name),'#101010')
            lines.append(f'color("{color}") translate([0,0,{z}]) import("part-{i}.stl");')
        return '\n'.join(lines)
    options=['--render','--colorscheme','Tomorrow Night','--imgsize','960,600','--camera',CAMERA]
    for n in range(16):
        scad=folder/f'{n:02}.scad';scad.write_text(script(n/15))
        openscad(command,scad,folder/f'{n:02}-raw.png',options)
    scad=folder/'mask.scad';scad.write_text(script(1,True));openscad(command,scad,folder/'mask.png',options)
    mask=np.array(Image.open(folder/'mask.png').convert('RGB')).astype(int)
    r,g,b=mask[:,:,0],mask[:,:,1],mask[:,:,2]
    selections={'CPU':(r>g*2+25)&(r>b*2+25),'VIDEO':(g>r*2+25)&(g>b*2+25),
                'DRIVES':(b>r*2+25)&(b>g*2+25),'PSU':(r>g*2+25)&(b>g*2+25)}
    targets={}
    for name,selection in selections.items():
        yy,xx=np.where(selection)
        if not len(xx):raise ValueError('Hidden cutaway component: '+name)
        targets[name]=(float(xx.mean())/6,float(yy.mean())/6)
    font=ImageFont.load_default(size=9)
    for n in range(16):
        raw=np.array(Image.open(folder/f'{n:02}-raw.png').convert('RGB'));raw[np.all(raw==[29,31,33],axis=2)]=0
        image=Image.fromarray(raw).resize((160,100),Image.Resampling.LANCZOS);d=ImageDraw.Draw(image)
        d.rectangle((0,0,159,13),fill='black');d.text((5,2),'INSIDE THE SYSTEM UNIT',font=font,fill='#dce4df')
        if n==15:
            for name,(x,y) in {'CPU':(3,76),'VIDEO':(3,19),'DRIVES':(111,78),'PSU':(129,18)}.items():
                width=d.textlength(name,font=font)
                d.line([(x+width/2,y+6),targets[name]],fill='#ffd58c')
                d.rectangle((x-1,y-1,x+width+1,y+11),fill='black')
                d.text((x,y),name,font=font,fill='#ffd58c')
        d.rectangle((0,0,159,99),outline='#dce4df');image.save(folder/f'{n:02}.png')
    (folder/'layout.json').write_text(json.dumps({'camera':CAMERA,'lid_lift_mm':600,'display_lift_mm':65,
        'targets':targets,'note':'Illustrative exploded view; source XY locations retained.'},indent=2)+'\n')
    stamp.write_text(signature)
