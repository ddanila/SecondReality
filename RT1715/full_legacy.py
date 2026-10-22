"""Host adaptations retaining original real-mode effect choreography."""
from pathlib import Path
import re
import json
import hashlib
import trimesh
import keycaps
import shutil
import subprocess
import numpy as np
from PIL import Image,ImageDraw
from build import HERE,ROOT,tool


def compile_c(source, output, name, objects, libraries=()):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    source=source.replace('#include "..\\dis\\dis.h"','#include "dis.h"')
    source='#include <string.h>\n'+source
    # Original MSC code assumes ASM globals may live outside DGROUP.
    # Watcom requires explicit far storage for scalar and pointer variables.
    for variable in ('lightshift','asmtestmode','_ndebug1','dotnum','gravity','gravitybottom','gravityd','cameralevel'):
        source=re.sub(r'(extern\s+(?:int|char)\s+)'+variable+r'\s*;',r'\1far '+variable+';',source)
    source=source.replace('extern int rotsin,rotcos;','extern int far rotsin,far rotcos;')
    source=source.replace('extern int bpmin,bpmax;','extern int far bpmin,far bpmax;')
    for variable in ('bgpic','wave1','wave2','vbuf'):
        source=re.sub(r'(extern\s+(?:unsigned\s+)?(?:int|char)\s*\*)'+variable+r'\s*;',r'\1 far '+variable+';',source)
    source=re.sub(r'\basm\b','_asm',source)
    (output/'MAIN.C').write_text(source,encoding='cp437')
    shutil.copyfile(ROOT/'DIS/DIS.H',output/'dis.h')
    wc=ROOT.parent/'msdos/watcom'
    subprocess.run([tool('wcc'),'-zq','-w=0','-bt=dos','-ml','-3','-os','-s','-ecc',f'-i={wc/"h"}','-fo=MAIN.OBJ','MAIN.C'],cwd=output,check=True)
    args=[tool('wlink'),'format','dos','option','quiet','option','stack=8192','option',f'map={name}.MAP','name',name+'.EXE','file','MAIN.OBJ']
    for p in objects:args+=['file',str(p)]
    for p in libraries:args+=['library',str(p)]
    args+=['libpath',str(wc/'lib286/dos'),'libpath',str(wc/'lib286')]
    executable=output/(name+'.EXE')
    executable.unlink(missing_ok=True)
    subprocess.run(args,cwd=output,check=True)
    if not executable.is_file():raise RuntimeError('Linker did not create '+str(executable))
    return executable


def data_object(data,label,output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    asm=f'.model large\n{label}_data segment para public "FAR_DATA"\npublic _{label}\n_{label} label byte\n'
    asm+='\n'.join('db '+','.join(map(str,data[i:i+32])) for i in range(0,len(data),32))+f'\n{label}_data ends\nend\n'
    (output/'DATA.ASM').write_text(asm)
    subprocess.run([tool('jwasm'),'-q','-Cp','-omf','-FoDATA.OBJ','DATA.ASM'],cwd=output,check=True)
    return output/'DATA.OBJ'


def keycap(output):
    source=(ROOT/'GLENZ/MAIN.C').read_text(encoding='cp437')
    source=source.replace('ceasypolylist(int *polylist,int *polys,long *points3)', 'ceasypolylist(int *polylist,int *polys,int *points3)')
    # Sample the real keycap envelope from the same model as the flyover.
    root=ROOT.parent/'3d-models/models/robotron-1715m/browser'
    metadata=json.loads((root/'model.json').read_text())
    key=next(k for k in metadata['keys'] if k['label']=='1')
    records={r['name']:r for r in metadata['keyMeshes']}
    pieces=[]; provenance={}
    for field in ('mesh','coreMesh','insertMesh'):
        if not key.get(field):continue
        record=records[key[field]];path=root/record['file']
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest!=record['sha256']:raise ValueError('Stale key source '+str(path))
        pieces.append(trimesh.load(path,force='mesh'));provenance[record['file']]=digest
    cap=trimesh.util.concatenate(pieces)
    lo,hi=cap.bounds;center=(lo+hi)/2;half=(hi-lo)/2
    def ring(level,top=False):
        result=[]
        for angle in np.arange(16)*np.pi/8:
            direction=np.array([np.cos(angle),np.sin(angle),0.])
            origin=np.array([*center[:2],level])
            point=origin+direction*max(keycaps.hits(cap,origin,direction))
            if top:point[2]=keycaps.height(cap,*point[:2])
            result.append(point)
        return result
    # Keep the square skirt and the raised ROUND body as separate steps.
    # A single taper between bottom and top erased the distinctive shoulder.
    vertices=ring(lo[2]+.001)+ring(hi[2]-.4,True)
    vertices.append(np.array([*center[:2],keycaps.height(cap,*center[:2])]))
    faces=[([16+i,16+(i+1)%16,32],9) for i in range(16)]
    faces += [(list(range(15,-1,-1)),10)]
    # One clear legend, flush to the dish. Top triangles use one shade so
    # source sampling does not turn the key into a patchwork of triangles.
    for x0,y0,x1,y1 in ((-.8,-3.5,.8,3.5),(-2.4,2,.0,3.5)):
        ids=[]
        for x,y in ((x0,y0),(x1,y0),(x1,y1),(x0,y1)):
            x+=center[0];y+=center[1];ids.append(len(vertices))
            vertices.append(np.array([x,y,keycaps.height(cap,x,y)+.06]))
        faces.append((ids,14))
    vertices+=ring(lo[2]+5.699)+ring(lo[2]+6.201)
    body=[]
    for lower,upper in ((0,41),(41,57),(57,16)):
        for i in range(16):
            body.append(([lower+i,lower+(i+1)%16,upper+(i+1)%16,upper+i],1+i//2))
    faces=body+faces
    scale=10000/max(hi-lo)
    points=np.rint((np.array(vertices)-center)*scale).astype(int)
    payload=str(len(points))+','+','.join(str(v) for row in points for v in row)
    for name in ('points','points1','points9','points8','points7','pointsb'):
        source,n=re.subn(r'long\s+'+name+r'\[64\]=\{.*?\};','long '+name+'[256]={'+payload+'};',source,flags=re.S)
        if n!=1:raise ValueError('Missing key geometry anchor '+name)
    for name in ('epolys','epolysb'):
        polys=','.join(str(v) for i,(face,color) in enumerate(faces[:-2]) for v in [len(face),0x4000+(4*color if name=='epolys' else 2+2*(i%2)),*face])+',0'
        source,n=re.subn(r'int '+name+r'\[\]=\{.*?\};','int '+name+'[]={'+polys+'};',source,flags=re.S)
        if n!=1:raise ValueError('Missing key face anchor')
    source=source.replace('int polylist[256];','int polylist[4096];')
    source=source.replace('char tmppal[768];',(HERE/'full-scenes/keycap-legend.c').read_text()+'\nchar tmppal[768];')
    source=source.replace('        cglenzinit();','        rt_legend_restore();cglenzinit();')
    source=source.replace('        rt_legend_restore();cglenzinit();','        rt_legend_restore();rt_legend_ready=0;cglenzinit();')
    source=source.replace('ceasypolylist(polylist,epolys,points3);','rt_legend_capture(points3);ceasypolylist(polylist,epolys,points3);')
    source=source.replace('        cglenzdone();','        cglenzdone();rt_legend_draw();')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    (output/'key-source.json').write_text(json.dumps(provenance,indent=2)+'\n')
    # Replace the original perspective checkerboard sprite with PCB traces.
    raw=bytearray((ROOT/'GLENZ/FC.UH').read_bytes())
    pic=Image.new('P',(320,200),0);d=ImageDraw.Draw(pic)
    # Broad alternating solder-mask tiles retain the readable checker rhythm.
    # Copper routes and large pads give it a PCB identity at 320x200.
    rows=(0,3,8,16,28,44,66,99)
    def project(x,y):return (round(160+(x-160)*(.08+.92*y/99)),y)
    for j,(y0,y1) in enumerate(zip(rows,rows[1:])):
        for i,x in enumerate(range(-800,1120,80)):
            d.polygon([project(x,y0),project(x+80,y0),project(x+80,y1),project(x,y1)],fill=2+((i+j)&1))
            if (i+j)%3==0:
                a=project(x+18,y0);b=project(x+18,(y0+y1)//2);c=project(x+60,(y0+y1)//2)
                d.line([a,b,c],fill=5,width=1 if y1<44 else 2)
                r=1 if y1<44 else 2
                d.rectangle((c[0]-r,c[1]-r,c[0]+r,c[1]+r),fill=6)
    palette=[(0,0,0),(3,9,5),(8,23,12),(15,36,20),(22,41,25),(43,31,12),(58,46,24),(34,49,34)]
    palette += [tuple(min(63,c+12) for c in p) for p in palette]
    raw[16:64]=bytes(c for p in palette for c in p)
    raw[784:64784]=pic.tobytes()
    obj=data_object(raw,'fc',output)
    zoom=(ROOT/'GLENZ/ZOOMER.C').read_text(encoding='cp437').replace('#include "..\\dis\\dis.h"','#include "dis.h"')
    (output/'ZOOMER.C').write_text(zoom,encoding='cp437')
    shutil.copyfile(ROOT/'DIS/DIS.H',output/'dis.h')
    wc=ROOT.parent/'msdos/watcom'
    subprocess.run([tool('wcc'),'-zq','-w=0','-bt=dos','-ml','-3','-os','-s','-ecc',f'-i={wc/"h"}','-fo=ZOOMER.OBJ','ZOOMER.C'],cwd=output,check=True)
    from renderer import assembly
    vec='OPTION NOKEYWORD:<xadd>\n'+assembly(ROOT/'GLENZ/VEC.ASM')
    vec=vec.replace('movzx\tbx,es:[bx-2]','movzx bx,byte ptr es:[bx-2]')
    # Several facets share a material now. Stable banks prevent a back-facing
    # facet from freeing the bank used by a visible facet in the same frame.
    vec,n=re.subn(r'movzx bx,byte ptr es:\[bx-2\].*?local_demo_glz_rc1:\s*pop\s+bx',
               'movzx bx,byte ptr es:[bx-2]\n\tmov al,bl\n\tshr al,1\n\tpop bx',vec,flags=re.S)
    if n!=1:raise ValueError('Missing keycap material bank allocator')
    vec=vec.replace('mov\tcl,7\n\tshrd\tax,dx,cl','mov\tcl,5\n\tshrd\tax,dx,cl').replace('shrd\tax,dx,8','shrd\tax,dx,6')
    vec=re.sub(r'(?m)^(\s*)loop\s+(\w+)\s*$',r'\1dec cx\n\1jnz \2',vec)
    (output/'VEC.ASM').write_text(vec,encoding='cp437')
    subprocess.run([tool('jwasm'),'-q','-Cp','-omf','-FoVEC.OBJ','VEC.ASM'],cwd=output,check=True)
    objects=[ROOT/'GLENZ'/(n+'.OBJ') for n in ('VID','ZOOM','ADATA','ASM','MATH')]+[output/'ZOOMER.OBJ',output/'VEC.OBJ']
    objects += [obj,ROOT/'DIS/DISC.OBJ']
    return compile_c(source,output,'GLENZ',objects,[ROOT/'GLENZ/GL10.LIB'])

if __name__=='__main__':print(keycap(HERE/'build/full-keycap'))


def interference(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    source=(ROOT/'TECHNO/KOE.C').read_text(encoding='cp437')
    source=source.replace('dis_musrow()','dis_musrow(0)').replace('mov ah,pl','mov ah,byte ptr pl')
    source=source.replace('<sys\\types.h>','<sys/types.h>').replace('<sys\\stat.h>','<sys/stat.h>')
    source=source.replace('#include <graph.h>','#include <conio.h>\n#include <stdlib.h>\n#include <dos.h>')
    # Phosphor luminance follows the original beat palette envelopes.
    a=source.index('\t\t\tswitch(x)');b=source.index('\t\t\tp-=3;',a)
    source=source[:a]+'''            *(p++)=x*3;
            *(p++)=x*12;
            *(p++)=x*5;
'''+source[b:]
    shutil.copyfile(HERE/'build/full-art-built/title/readp.c',output/'readp.c')
    source=source.replace('_asm add word ptr p[2],40000/16','p=(char huge *)pic+40000L;')
    from renderer import assembly
    asm=assembly(ROOT/'TECHNO/KOEB.ASM')
    asm=re.sub(r'(local_\w+:)\s*(zzz=)',r'\1\n\2',asm)
    start=asm.index('pal0 LABEL');end=asm.index('sinuspower',start)
    region=asm[start:end]
    def phosphor(match):
        light=int(match[1]);return 'db '+','.join(map(str,(light//4,light,light//2)))
    region=re.sub(r'db\s+(\d+),\s*\d+\*[67]/9,\s*\d+',phosphor,region)
    region=region.replace('0,30,40','6,40,14')
    asm=asm[:start]+region+asm[end:]
    (output/'CIRCLES.ASM').write_text(asm,encoding='cp437')
    subprocess.run([tool('jwasm'),'-q','-Cp','-omf','-FoCIRCLES.OBJ','CIRCLES.ASM'],cwd=output,check=True)
    # The first circular layer has its own palette in KOEA. Preserve its
    # released assembly code, patching OMF data records and their checksums.
    raw=(ROOT/'TECHNO/KOEA.OBJ').read_bytes();result=bytearray();at=0;counts=[0,0]
    palettes=[]
    for levels,weight in [([0,10,20,30,40,50,60,30]*2,7),([30,60,50,40,30,20,10,0]*2,8)]:
        palettes.append((bytes(v for light in levels for v in (light,light*weight//9,light)),
                         bytes(v for light in levels for v in (light//4,light,light//2))))
    while at<len(raw):
        length=int.from_bytes(raw[at+1:at+3],'little');end=at+3+length
        if length<1 or end>len(raw):raise ValueError('Invalid OMF record')
        record=bytearray(raw[at:end])
        for i,(old,new) in enumerate(palettes):
            count=record[3:-1].count(old);counts[i]+=count
            if count:record[3:-1]=record[3:-1].replace(old,new)
        record[-1]=(-sum(record[:-1]))&255;result.extend(record);at=end
    if counts!=[1,1]:raise ValueError('Circular palette anchors changed: '+str(counts))
    (output/'PHOSPHOR.OBJ').write_bytes(result)
    objects=[ROOT/'TECHNO'/n for n in ('_CIRCLE.OBK','_CIRCLE2.OBK')]+[output/'PHOSPHOR.OBJ',output/'CIRCLES.OBJ',ROOT/'DIS/DISC.OBJ']
    return compile_c(source,output,'TECHNO',objects)


def tunnel(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    import math,struct
    # Eight visual conductor bundles, eight points per bundle. No claim about
    # physical wire count; radii/centres retain the original perspective table.
    old=np.frombuffer((ROOT/'TUNNELI/TUNNEL.DAT').read_bytes(),dtype='<i2').reshape(138,64,2)
    table=old.copy()
    for radius in range(138):
        cx=float(old[radius,:,0].mean());cy=float(old[radius,:,1].mean())
        rx=float(np.ptp(old[radius,:,0]))/2;ry=float(np.ptp(old[radius,:,1]))/2
        for j in range(64):
            angle=2*math.pi*(j//8)/8
            strand=2*math.pi*(j%8)/8
            table[radius,j]=round(cx+(.70*math.sin(angle)+.14*math.sin(strand))*rx),round(cy+(.70*math.cos(angle)+.14*math.cos(strand))*ry)
    ring=data_object(table.astype('<i2').tobytes(),'ringxy',output/'rings')
    motion=data_object((ROOT/'TUNNELI/SINIT.DAT').read_bytes(),'motion',output/'motion')
    source=(HERE/'full-scenes/tunnel.c').read_text()
    return compile_c(source,output,'TUNNELI',[ring,motion,ROOT/'DIS/DISC.OBJ'])


def dots(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    font=(HERE/'assets/full-demo/dots/tosm-chargen.bin').read_bytes()
    # 640 remains below the original assembly's 1024-dot allocation.
    # Wider, centered slices make the word depth visible during rotation.
    targets=[]
    targets.append([((i%32-15.5)*650+((i%32)//8-1.5)*1400,(i//32-9.5)*800,0) for i in range(640)])
    for word in ('U880','1715'):
        pixels=[]
        for c,char in enumerate(word):
            for y in range(12):
                bits=font[y*128+ord(char)]
                for x in range(8):
                    if bits&(128>>x):pixels.append(((c*9+x-17)*750,(y-5.5)*1100))
        if not pixels:raise ValueError('Empty glyphs in captured character RAM')
        targets.append([(*pixels[i%len(pixels)],((i//len(pixels))-((639//len(pixels))/2))*600) for i in range(640)])
    (output/'FORM.H').write_text('static int far forms[3][640][3]={'+','.join('{'+','.join('{'+','.join(str(round(v)) for v in point)+'}' for point in form)+'}' for form in targets)+'};\n')
    source=(ROOT/'DOTS/MAIN.C').read_text(encoding='cp437')
    source=source.replace('dotnum=512;','dotnum=640;')
    source=source.replace('mov\tal,color','mov\tal,byte ptr color')
    source=source.replace('int\tdottaul[1024];','int\tdottaul[1024];\n#include "FORM.H"')
    source=source.replace('int\ta,b,c,d,i,j,mode;','int\ta,b,c,d,i,j=0,mode;')
    source=source.replace('4,25,30,\n8,40,45,\n16,55,60','4,25,8,\n8,40,14,\n16,60,24')
    a=source.index('\t\t\telse if(frame<900)');b=source.index('\t\t\telse if(frame<2400)',a)
    source=source[:a]+source[b:]
    source=source.replace('else if(frame<2400)','else if(frame>=2360 && frame<2400)').replace('else if(frame<2440)','else if(frame>=2400 && frame<2440)')
    source=source.replace('\t\tdrawdots();','''        if(frame>=500 && frame<2360) {
            int form=frame<1000?0:(frame<1700?1:2);
            int local=frame-(form==0?500:(form==1?1000:1700));
            int burst=local<120?120-local:(local>510?local-510:0);
            int turn=isin(frame*3)/3,cs=icos(turn),sn=isin(turn);
            for(a=0;a<640;a++) {
                long xx=forms[form][a][0],yy=forms[form][a][1];
                int tx=(xx*cs-yy*sn)/256+isin(frame*2)*6;
                int ty=(xx*sn+yy*cs)/256+icos(frame*3)*3;
                int tz=forms[form][a][2]+isin(frame*4+a*3)*2;
                tx+=(long)isin(a*37+frame*5)*burst/8;
                ty+=(long)icos(a*29+frame*4)*burst/12;
                tz+=(long)isin(a*17+frame*6)*burst/8;
                dot[a].x+=(tx-dot[a].x)/8;
                dot[a].y+=(ty-dot[a].y)/8;
                dot[a].z+=(tz-dot[a].z)/8;
                dot[a].yadd=0;
            }
            gravity=0;rotcos=icos(isin(frame*2)/3)*64;rotsin=isin(isin(frame*2)/3)*64;
        }
        drawdots();''')
    from renderer import assembly
    asm=assembly(ROOT/'DOTS/ASM.ASM')
    asm=asm.replace('add\tbp,9000','add\tbp,9000\n    cmp bp,128\n    jle local__drawdots_z')
    asm=re.sub(r'(?m)^(\s*)loop\s+(\w+)\s*$',r'\1dec cx\n\1jnz \2',asm)
    (output/'DRAW.ASM').write_text(asm,encoding='cp437')
    subprocess.run([tool('jwasm'),'-q','-Cp','-omf','-FoDRAW.OBJ','DRAW.ASM'],cwd=output,check=True)
    return compile_c(source,output,'MINVBALL',[output/'DRAW.OBJ',ROOT/'DIS/DISC.OBJ'])
