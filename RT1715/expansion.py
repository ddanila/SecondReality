#!/usr/bin/env python3
"""Host-build optional Robotron chapters and isolated DOS cuts.

The tested short runtime is copied, never edited. Effect pixels are drawn live
in DOS; host assets are source board images, glyphs, geometry and timing tables.
"""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess

from PIL import Image, ImageDraw, ImageFont
import numpy as np
from build import HERE, ROOT, tool, masm_source
from music import timeline, module_archive

CONFIG = HERE/'assets/robotron/expansion.json'
SPEC = json.loads(CONFIG.read_text())
if SPEC.get('version') != 1:raise ValueError('Unsupported expansion manifest')
if sorted(s['renderer_id'] for s in SPEC['scenes']) != list(range(len(SPEC['scenes']))):
    raise ValueError('Effect renderer IDs must be unique and contiguous')
SCENES = [s['id'] for s in sorted(SPEC['scenes'],key=lambda s:s['renderer_id'])]
INTRO, POST, STUDIES = (SPEC[k] for k in ('intro','post','studies'))


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def image_asset(path,mask=None):
    from PIL import ImageOps
    image=Image.open(path).convert('RGB')
    raw=np.array(image);raw[np.all(raw==[29,31,33],axis=2)]=0
    image=Image.fromarray(raw)
    bounds=image.getbbox()
    if mask:
        m=np.asarray(Image.open(mask).convert('RGB')).astype(int)
        yy,xx=np.where((m[:,:,0]>m[:,:,1]*2+30)&(m[:,:,2]>m[:,:,1]*2+30))
        if not len(xx):raise ValueError('Missing image focus '+str(mask))
        bounds=(max(0,int(xx.min())-24),max(0,int(yy.min())-24),
                min(image.width,int(xx.max())+25),min(image.height,int(yy.max())+25))
    image=image.crop(bounds)
    fitted=ImageOps.contain(image,(620,380),Image.Resampling.LANCZOS)
    canvas=Image.new('RGB',(640,400));canvas.paste(fitted,((640-fitted.width)//2,(400-fitted.height)//2))
    grey=np.asarray(canvas,dtype=np.float64) @ np.array([.2126,.7152,.0722])
    return np.where(grey<2,0,np.clip(np.rint(grey*119/255)+8,8,127)).astype('uint8').tobytes()


def write_assets(output,source):
    output=Path(output).resolve()
    from presentation import load
    _,root,files=load(source=source)
    # Use the current source rather than trusting a previous build's PNG cache.
    from credit_scene import load_scene
    from credit_views import render_cards
    assetdir=output/'art';assetdir.mkdir(exist_ok=True)
    records,loader,chips,keys=load_scene(root,assetdir,'openscad')
    for name in ['cpu','main-ram','display-ram']:
        render_cards(files['credits'],assetdir,records,loader,chips,keys,'openscad',only=name,context=True)
    from crt_transition import prepare as prepare_crt
    shutil.copyfile(prepare_crt(assetdir,records,loader,keys),output/'FX.CRT')
    # Locator is a complete motherboard; detail views use the same source.
    labels=('cpu','main-ram','display-ram')
    names=[name+'-locator.png' for name in labels]+[name+'-photo.png' for name in labels]
    payload=b''.join(image_asset(assetdir/name) for name in names[:3])
    payload+=b''.join(image_asset(assetdir/(name+'-photo.png'),assetdir/(name+'-annotation.png')) for name in labels)
    (output/'FX.IMG').write_bytes(payload)
    locations=[]
    from PIL import ImageOps
    for name in labels:
        raw=np.array(Image.open(assetdir/(name+'-locator.png')).convert('RGB'))
        raw[np.all(raw==[29,31,33],axis=2)]=0
        im=Image.fromarray(raw);bounds=im.getbbox();cropped=im.crop(bounds)
        fitted=ImageOps.contain(cropped,(620,380),Image.Resampling.LANCZOS)
        m=np.array(Image.open(assetdir/(name+'-locator-mask.png')).convert('RGB')).astype(int)
        yy,xx=np.where((m[:,:,0]>m[:,:,1]*2+30)&(m[:,:,2]>m[:,:,1]*2+30))
        if not len(xx):raise ValueError('Missing component locator')
        locations.extend([(float(xx.mean())-bounds[0])*fitted.width/cropped.width+(640-fitted.width)/2,
                          (float(yy.mean())-bounds[1])*fitted.height/cropped.height+(400-fitted.height)/2])
    (output/'FX.LOC').write_bytes(struct.pack('<6f',*locations))
    font=ImageFont.load_default(size=9)
    glyphs=bytearray()
    for c in range(32,127):
        im=Image.new('L',(8,12));ImageDraw.Draw(im).text((0,-1),chr(c),font=font,fill=255)
        glyphs.extend((np.asarray(im)>96).astype('uint8').tobytes())
    (output/'FX.FNT').write_bytes(glyphs)
    # Deterministic point targets sampled from a title; C projects and morphs them.
    title=Image.new('L',(320,200));d=ImageDraw.Draw(title)
    large=ImageFont.load_default(size=37)
    for text,y in [('robotron',62),('1715M',109)]:
        width=d.textbbox((0,0),text,font=large)[2];d.text(((320-width)//2,y),text,font=large,fill=255)
    coords=np.argwhere(np.asarray(title)>128)[::2]
    (output/'FX.PTS').write_bytes(struct.pack('<I',len(coords))+b''.join(struct.pack('<hh',int(x),int(y)) for y,x in coords))
    # Source-derived assembly envelopes for the translucent-shell study.
    groups=[('case-lid',0),('logic-boards-motherboard',1),('logic-boards-display-controller',2),('drives',3)]
    boxes=[]
    for name,kind in groups:
        if name not in records:
            matches=[n for n in records if (n.startswith('logic-') and n.endswith(name.removeprefix('logic-board-')))] if kind in (1,2) else []
            if not matches: raise ValueError('Missing assembly source '+name)
            name=matches[0]
        bounds=loader(records[name]).bounds
        boxes.append((name,kind,bounds.tolist()))
    for instance,body,leads in chips:
        kind=4 if instance['board']=='motherboard' else 5
        boxes.append((instance['id'],kind,body.bounds.tolist()))
    if len(boxes)>512:raise ValueError('Assembly exceeds the effect geometry budget')
    (output/'FX.GEO').write_bytes(struct.pack('<I',len(boxes))+b''.join(struct.pack('<I6f',kind,*np.array(bounds).flatten()) for _,kind,bounds in boxes))
    from effect_mesh import write as write_mesh
    mesh_evidence=write_mesh(output/'FX.MSH',records,loader,chips,keys,files['flight'])
    evidence={'mesh':mesh_evidence,'source':str(root),'model_sha256':digest(root/'browser/model.json'),
              'scad_sha256':{str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*.scad'))},
              'images':{n:digest(assetdir/n) for n in names},
              'assets_sha256':{n:digest(output/n) for n in ('FX.IMG','FX.FNT','FX.PTS','FX.GEO','FX.LOC','FX.CRT','FX.MSH')},
              'assembly_envelopes':boxes,
              'interpretation':'Abstract data paths and simplified assembly envelopes; not electrical or service simulations.'}
    (output/'source.json').write_text(json.dumps(evidence,indent=2)+'\n')


def write_schedule(path,scenes):
    if not scenes or len(scenes)>16:raise ValueError('Invalid effect scene count')
    previous=None
    for name,a,b,c,d in scenes:
        if name not in SCENES or not 0<=a<=c<256 or not 0<=b<64 or not 0<=d<64 or (a,b)>=(c,d):
            raise ValueError('Invalid effect scene cue')
        if previous and previous!=(a,b):raise ValueError('Effect scenes must be contiguous')
        previous=(c,d)
    first=min(s[1] for s in scenes);last=max(s[3] for s in scenes)
    rows=timeline(ROOT/'MAIN/MUSIC1.S3M',first,last)
    times={(r['order'],r['row']):round(r['seconds']*1000) for r in rows}
    clock=[];previous=0
    for order in range(first,last+1):
        for row in range(64):
            previous=times.get((order,row),previous);clock.append(previous)
    entries=[]
    for name,a,b,c,d in scenes:
        if (a,b) not in times or (c,d) not in times: raise ValueError('Unreachable effect cue')
        entries.append((SCENES.index(name),a*64+b,c*64+d,times[a,b],times[c,d]))
    data=struct.pack('<4s4I',b'FX01',first,last,len(entries),len(clock))
    data+=struct.pack('<'+'I'*len(clock),*clock)
    data+=b''.join(struct.pack('<5I',*entry) for entry in entries)
    path.write_bytes(data)
    return [{'scene':s[0],'entry':list(s[1:3]),'exit':list(s[3:5]),'milliseconds':e[4]-e[3]} for s,e in zip(scenes,entries)]


def launcher(cut,scene=None):
    code=masm_source(True,True)
    start=42 if cut!='scene' else 42
    # Start MUSIC1 directly, avoiding a burst of the flight soundtrack first.
    code=code.replace('mov\tax,0\n        mov     bx,-1','mov\tax,1\n        mov     bx,-1')
    code=code.replace('push    18 ; city music entry (decimal order index)',f'push    {start} ; expansion MUSIC1 entry')
    code=code.replace('mov dx,OFFSET exe19','mov dx,si')
    code=code.replace("exe19                                           db 'U2E.EXE',0", "exefx db 'FX.EXE',0\nexepost db 'POST.EXE',0\nexe19                                           db 'U2E.EXE',0")
    begin='''        mov si,OFFSET exefx
        call rt_exec32
        jc local_global_rt_exp_fail
        mov ah,4dh
        int 21h
        or al,al
        jnz local_global_rt_exp_fail
'''
    reset='''        mov ax,0
        mov bx,18
        mov cx,45000
        call restartmus
'''
    anchor='        mov     si,OFFSET exe19       ; VISU/C/U2E.C: city flyover'
    if anchor not in code:raise ValueError('Launcher source anchor changed')
    code=code.replace(anchor,begin+('        jmp local_global_rt_sequence_done\n' if cut in ('scene','studies') else reset)+anchor)
    if cut=='extended':
        anchor='        mov     si,OFFSET exe22       ; CREDITS/MAIN.C: illustrated cards'
        code=code.replace(anchor,'''        mov ax,1
        mov bx,60
        mov cx,48700
        call restartmus
        mov si,OFFSET exepost
        call rt_exec32
        jc local_global_rt_exp_fail
        mov ah,4dh
        int 21h
        or al,al
        jnz local_global_rt_exp_fail
        mov ax,0
        mov bx,28
        mov cx,45000
        call restartmus
'''+anchor)
    # STMIK's order field changes on the next mixer tick after _zplaysong.
    # Never let a newly executed part observe the previous module's late order.
    helper = """rt_exp_wait PROC NEAR
        push es
        push bp
        push di
        mov bp,ax
        mov di,210
rt_exp_wait_loop:
        mov bx,1
        int 0fch
        mov es,cs:stmikseg
        cmp es:_np_ord,bp
        je rt_exp_wait_ok
        dec di
        jnz rt_exp_wait_loop
        pop di
        pop bp
        pop es
        stc
        ret
rt_exp_wait_ok:
        pop di
        pop bp
        pop es
        clc
        ret
rt_exp_wait ENDP
"""
    code=code.replace('rt_exec32 PROC NEAR',helper+'\nrt_exec32 PROC NEAR')
    for order, speed in [(18,45000),(60,48700),(28,45000)]:
        marker=f'mov bx,{order}\n        mov cx,{speed}\n        call restartmus'
        code=code.replace(marker,marker+f'\n        mov ax,{order}\n        call rt_exp_wait\n        jc local_global_rt_exp_fail')
    code=code.replace('local_global_rt_sequence_done:', '''        jmp local_global_rt_sequence_done
local_global_rt_exp_fail:
        mov cs:errorcode,8
local_global_rt_sequence_done:''')
    return code


def build(args):
    output=args.output.resolve();dos=output/'dos';output.mkdir(parents=True,exist_ok=True)
    source=args.base.resolve()
    if source==dos or source in dos.parents:raise ValueError('Use an isolated output directory')
    if (source/'EXPAND.JSON').exists():raise ValueError('Use the preserved short runtime as --base')
    # Copy only the validated runtime, not previous capture and scratch files.
    if dos.exists():shutil.rmtree(dos)
    shutil.copytree(source,dos)
    shutil.copyfile(source/"RT1715.EXE",dos/"SHORT.EXE")
    if args.assets_from:
        from presentation import load
        _, root, _ = load(source=args.model_source)
        previous=json.loads((args.assets_from/'source.json').read_text())
        current={str(p.relative_to(root)):digest(p) for p in sorted(root.rglob('*.scad'))}
        if previous['scad_sha256']!=current or previous['model_sha256']!=digest(root/'browser/model.json'):
            raise ValueError('Reusable chapter assets have stale model sources')
        for name, expected in previous.get('assets_sha256',{}).items():
            if digest(args.assets_from/name)!=expected:raise ValueError('Reusable chapter asset changed: '+name)
        for name in ('FX.IMG','FX.FNT','FX.PTS','FX.GEO','FX.LOC','FX.CRT','FX.MSH','source.json'):
            shutil.copyfile(args.assets_from/name,output/name)
    else:
        write_assets(output,args.model_source)
    for name in ('FX.IMG','FX.FNT','FX.PTS','FX.GEO','FX.LOC','FX.CRT','FX.MSH'):shutil.copyfile(output/name,dos/name)
    # Cache only visibility, retaining live projection and depth drawing in DOS.
    recipe=digest(HERE/'effects.c')+digest(HERE/'bake_effect_visibility.py')+digest(output/'FX.MSH')
    evidence=json.loads((output/'source.json').read_text())
    if args.assets_from and previous.get('visibility_recipe')==recipe:
        for name in ('FX.VIS','FX.DRW'):shutil.copyfile(args.assets_from/name,output/name)
    else:
        from bake_effect_visibility import bake
        bake(dos,output/'FX.VIS')
    for name in ('FX.VIS','FX.DRW'):
        shutil.copyfile(output/name,dos/name)
        evidence['assets_sha256'][name]=digest(output/name)
    evidence['visibility_recipe']=recipe
    evidence['interpretation']='Source geometry and conceptual data flow; not an electrical simulation.'
    (output/'source.json').write_text(json.dumps(evidence,indent=2)+'\n')
    schedule=[(args.scene,42,0,44,0)] if args.cut=='scene' else (STUDIES if args.cut=='studies' else INTRO)
    manifest={'version':1,'cut':args.cut,'module':'MUSIC1','spec_sha256':digest(CONFIG),'intro':write_schedule(dos/'FX.TIM',schedule),
              'post':write_schedule(dos/'POST.TIM',POST) if args.cut=='extended' else [],
              'source_sha256':digest(output/'source.json')}
    watcom=HERE/'build/toolchain/watcom'
    compiler=next((watcom/p for p in ('armo64/wcc386','binl64/wcc386','binl/wcc386') if (watcom/p).is_file()),None)
    if compiler is None:raise ValueError('Install the native protected-mode toolchain first')
    assembler=tool('jwasm');linker=tool('wlink')
    for name in ['FX']+(['POST'] if args.cut=='extended' else []):
        subprocess.run([str(compiler),'-zq','-bt=dos','-mf','-3r','-ot','-s','-ecc',f'-i={watcom/"h"}',
                        f'-dFX_POST={int(name=="POST")}',f'-fo={output/name}.OBJ',str(HERE/'effects.c')],check=True)
        subprocess.run([linker,'format','os2','le','option','quiet','option','stack=65536','option',
                        f'stub={watcom/"binw/dos32a.exe"}','name',str(dos/(name+'.EXE')),'file',str(output/(name+'.OBJ')),
                        'libpath',str(watcom/'lib386/dos'),'libpath',str(watcom/'lib386')],check=True)
    (output/'RT1715.ASM').write_text(launcher(args.cut,args.scene),encoding='cp437')
    subprocess.run([assembler,'-q','-Cp','-omf','-FoRT1715.OBJ','RT1715.ASM'],cwd=output,check=True)
    shutil.copyfile(ROOT/'MAIN/STMIK.300',output/'STMIK.OBJ')
    subprocess.run([linker,'format','dos','option','quiet','name','dos/RT1715.EXE','file','RT1715.OBJ','file','STMIK.OBJ'],cwd=output,check=True)
    (dos/'REALITY.FC').write_bytes(module_archive((ROOT/'MAIN/MUSIC0.S3M').read_bytes(),(ROOT/'MAIN/MUSIC1.S3M').read_bytes()))
    shutil.copyfile(output/'source.json',dos/'FXSOURCE.JSON')
    from flight_only import build as build_flight
    build_flight(dos)
    manifest['runtime_sha256']={p.name:digest(p) for p in dos.iterdir() if p.is_file() and (p.suffix in ('.EXE','.TIM','.IMG','.FNT','.PTS','.GEO','.LOC','.CRT','.MSH','.DRW','.VIS','.FC') or p.name=='FXSOURCE.JSON')}
    shutil.copyfile(output/'source.json',dos/'FXSOURCE.JSON')
    (dos/'EXPAND.JSON').write_text(json.dumps(manifest,indent=2)+'\n')
    print(dos)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,default=HERE/'build/dos')
    p.add_argument('--output',type=Path,default=HERE/'build/expanded')
    p.add_argument('--cut',choices=('expanded','extended','scene','studies'),default='expanded')
    p.add_argument('--scene',choices=SCENES,default='lens')
    p.add_argument('--model-source',type=Path)
    p.add_argument('--assets-from',type=Path,help='Reuse source-verified host artwork from a prior expansion build')
    build(p.parse_args())


if __name__=='__main__':main()
