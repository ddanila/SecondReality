"""Detailed, individually framed technical photographs from current meshes."""
import json
from pathlib import Path
import numpy as np
import trimesh
from PIL import Image, ImageOps, ImageDraw, ImageFont
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
        selected=[]; marked=set()
        for instance,m,leads in chips:
            if instance['board']==board:
                highlight=any(label in instance['label'] for label in view.get('highlight_chips',[]))
                if highlight or any(label in instance['label'] for label in view.get('focus_chips',[])):
                    marked.add(instance['id'])
                solids.append((instance['id'],m,'#c6a66a' if highlight else '#303333'))
                solids.append((instance['id']+'-pins',leads,'#a6aaa5'))
                if any(label in instance['label'] for label in view.get('focus_chips',[])):
                    selected.append(m)
        if view.get('keys'):
            solids.append(('keys',trimesh.util.concatenate(keys),'#dddccb'))
        if view.get('focus_parts'):
            selected.extend(m for n,m,color in solids if n in view['focus_parts'])
            marked.update(view['focus_parts'])
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
        script=[]; mask_script=[]; full_script=[]; full_mask=[]
        for i,(label,m,color) in enumerate(solids):
            path=output/f'{name}-{i}.stl';m.export(path)
            shape=f'import({json.dumps(str(path))});'
            mask_color='#ff00ff' if label in marked else '#101010'
            full_script.append(f'color("{color}") {{ {shape} }}')
            full_mask.append(f'color("{mask_color}") {{ {shape} }}')
            if crop:
                lo,hi=np.array(crop[0]),np.array(crop[1])
                shape='intersection() { '+shape+' translate('+json.dumps(lo.tolist())+') cube('+json.dumps((hi-lo).tolist())+'); }'
            script.append(f'color("{color}") {{ {shape} }}')
            mask_color='#ff00ff' if label in marked else '#101010'
            mask_script.append(f'color("{mask_color}") {{ {shape} }}')
        if view.get('flip'):
            script=['rotate([180,0,0]) {',*script,'}']
            mask_script=['rotate([180,0,0]) {',*mask_script,'}']
            full_script=['rotate([180,0,0]) {',*full_script,'}']
            full_mask=['rotate([180,0,0]) {',*full_mask,'}']
        scad=output/f'{name}.scad';scad.write_text('\n'.join(script)+'\n')
        png=output/f'{name}.png'
        angle=view.get('angle',[55,0,35])
        camera=','.join(str(v) for v in [0,0,0,*angle,0])
        openscad(command,scad,png,['--render','--colorscheme','Tomorrow Night',
                 '--imgsize','960,600','--camera',camera,'--viewall','--autocenter'])
        pixels=np.array(Image.open(png).convert('RGB'))
        pixels[np.all(pixels==[29,31,33],axis=2)]=0
        rendered=Image.fromarray(pixels)
        locator=None
        if crop and view.get('annotation') and view.get('locator',True):
            full_images=[]
            for suffix,lines in [('locator',full_script),('locator-mask',full_mask)]:
                fs=output/f'{name}-{suffix}.scad';fp=output/f'{name}-{suffix}.png'
                fs.write_text('\n'.join(lines)+'\n')
                openscad(command,fs,fp,['--render','--colorscheme','Tomorrow Night',
                         '--imgsize','960,600','--camera',camera,'--viewall','--autocenter'])
                raw=np.array(Image.open(fp).convert('RGB'));raw[np.all(raw==[29,31,33],axis=2)]=0
                full_images.append(Image.fromarray(raw))
            bounds=full_images[0].getbbox()
            overview=full_images[0].crop(bounds);target_mask=np.array(full_images[1].crop(bounds)).astype(int)
            yy0,xx0=np.where((target_mask[:,:,0]>target_mask[:,:,1]*2+30)&(target_mask[:,:,2]>target_mask[:,:,1]*2+30))
            locator=Image.new('RGB',(48,70),'black');thumb=ImageOps.contain(overview,(44,54))
            ox=(48-thumb.width)//2;oy=12+(54-thumb.height)//2
            locator.paste(thumb,(ox,oy));d=ImageDraw.Draw(locator)
            d.text((4,1),'BOARD',fill='white',font=ImageFont.load_default(size=8))
            if len(xx0):
                sx=thumb.width/overview.width;sy=thumb.height/overview.height
                d.rectangle((ox+int(xx0.min()*sx),oy+int(yy0.min()*sy),
                             ox+max(int(xx0.max()*sx),int(xx0.min()*sx)+2),
                             oy+max(int(yy0.max()*sy),int(yy0.min()*sy)+2)),outline='#ffd58c',width=1)
            d.rectangle((0,0,47,69),outline='#737777',width=1)
        if view.get('annotation'):
            mask_scad=output/f'{name}-annotation.scad'
            mask_png=output/f'{name}-annotation.png'
            mask_scad.write_text('\n'.join(mask_script)+'\n')
            openscad(command,mask_scad,mask_png,['--render','--colorscheme','Tomorrow Night',
                     '--imgsize','960,600','--camera',camera,'--viewall','--autocenter'])
            mask=np.array(Image.open(mask_png).convert('RGB')).astype(int)
            yy,xx=np.where((mask[:,:,0]>mask[:,:,1]*2+30)&(mask[:,:,2]>mask[:,:,1]*2+30))
            if not len(xx): raise ValueError(f'Annotation target is hidden: {name}')
            # Draw at the actual DOS picture resolution, then enlarge without
            # filtering; the converter reduces it back to 160x100.
            if locator:
                main=ImageOps.contain(rendered,(108,94),Image.Resampling.LANCZOS)
                small=Image.new('RGB',(160,100),'black');main_y=(100-main.height)//2
                small.paste(main,(0,main_y));small.paste(locator,(112,27))
                sx=main.width/960;sy=main.height/600
            else:
                small=rendered.resize((160,100),Image.Resampling.LANCZOS)
                sx=sy=1/6;main_y=0
            draw=ImageDraw.Draw(small);font=ImageFont.load_default(size=8)
            label=view['annotation'];target=(round(float(xx.mean())*sx),round(float(yy.mean())*sy)+main_y)
            width=round(draw.textlength(label,font=font))
            label_x=(104 if locator else 152)-width if target[0]>(54 if locator else 80) else 8
            if 'RAM' in label:
                x0,y0=max(3,round(float(xx.min())*sx)-2),max(16,round(float(yy.min())*sy)+main_y-2)
                x1,y1=min(156,round(float(xx.max())*sx)+2),min(96,round(float(yy.max())*sy)+main_y+2)
                for x,y,dx,dy in [(x0,y0,1,1),(x1,y0,-1,1),(x0,y1,1,-1),(x1,y1,-1,-1)]:
                    draw.line([(x+dx*4,y),(x,y),(x,y+dy*4)],fill='#ffd58c',width=1)
                target=(x1 if label_x>80 else x0,y0)
            else:
                x,y=target;draw.ellipse((x-2,y-2,x+2,y+2),outline='#ffd58c',width=1)
            draw.line([(label_x+width//2,13),(label_x+width//2,17),target],fill='white',width=1)
            draw.rectangle((label_x-3,3,label_x+width+3,13),fill='black')
            draw.text((label_x,3),label,fill='white',font=font)
            rendered=small.resize((960,600),Image.Resampling.NEAREST)
        im=ImageOps.contain(rendered,(948,588))
        canvas=Image.new('RGB',(960,600),'black')
        canvas.paste(im,((960-im.width)//2,(600-im.height)//2))
        ImageOps.expand(canvas,border=6,fill='white').resize((960,600)).save(png)
        result.append(dict(image=str(png),lines=card['lines'],hold_frames=200))
        report.append(dict(image=name,parts=names,focus_chips=view.get('focus_chips'),crop=crop,angle=angle))
    (output/'credit-views.json').write_text(json.dumps(report,indent=2)+'\n')
    return result
