"""Two-dimensional PCB height/color map for the original terrain ray caster."""
import hashlib,json,re,subprocess
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from build import HERE,ROOT,tool
from renderer import assembly
from full_legacy import compile_c,data_object


def maps():
    path=ROOT.parent/'3d-models/models/robotron-1715m/browser/model.json'
    raw=path.read_bytes();metadata=json.loads(raw);board=metadata['pcbComponents']['boards'][0]
    height=Image.new('L',(256,256),25);color=Image.new('L',(256,256),0)
    hd,cd=ImageDraw.Draw(height),ImageDraw.Draw(color)
    sx=248/board['size'][0];sy=248/board['size'][1]
    centers=[]
    for component in board['components']:
        x,y,_=component['position'];x=(x-board['origin'][0])*sx+4;y=(y-board['origin'][1])*sy+4
        centers.append((x,y))
    # Decorative routed channels link nearby projected package centres. They
    # are artistic patterns, not a claim about the motherboard's netlist.
    for i,(x,y) in enumerate(centers):
        if i==0:continue
        u,v=centers[i-1]
        cd.line([(x,y),(u,y),(u,v)],fill=96,width=1)
    for component,(x,y) in zip(board['components'],centers):
        match=re.fullmatch(r'DIP-(\d+)_W([\d.]+)mm',component['model'])
        if not match:continue
        pins=int(match[1]);pitch=float(match[2]);length=(pins/2-1)*2.54+3.5
        angle=np.deg2rad(component['rotation']);ca,sa=np.cos(angle),np.sin(angle)
        def polygon(x0,y0,x1,y1,h,material):
            p=[(x+(u*ca-v*sa)*sx,y+(u*sa+v*ca)*sy) for u,v in ((x0,y0),(x1,y0),(x1,y1),(x0,y1))]
            hd.polygon(p,fill=h);cd.polygon(p,fill=material)
        for side in (-1,1):
            for pin in range(pins//2):
                yy=(pin-(pins/2-1)/2)*2.54
                x0,x1=sorted((side*(pitch/2-1.2),side*(pitch/2+1.5)))
                polygon(x0,yy-.6,x1,yy+.6,33,64)
        polygon(-pitch/2+1,-length/2,pitch/2-1,length/2,80 if pins>=28 else 63,32)
    # Signed byte heights keep the original camera's vertical scale.
    h=(np.array(height,dtype=np.int16)-55).astype(np.int8).tobytes()
    return h,color.tobytes(),{'source':str(path),'sha256':hashlib.sha256(raw).hexdigest(),'board':board['name'],'packages':len(centers),'limitations':'Component positions inherit model photo-registration uncertainty; heights exaggerated; routes decorative.'}


def build(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    height,color,provenance=maps()
    tables=[data_object(data,name,output/name) for name,data in [('w1dta',height),('w2dta',color)]]
    source=(ROOT/'COMAN/MAIN.C').read_text(encoding='cp437').replace('char combg[16];','')
    (output/'wave.h').write_bytes((ROOT/'COMAN/WAVE.H').read_bytes())
    source=source.replace('vbuf=halloc(16384,4);','''for(a=0;a<128;a++) {
        int level=a&31, material=a>>5;
        if(material==0){palette[a*3]=level/5;palette[a*3+1]=8+level;palette[a*3+2]=level/3;}
        else if(material==1){palette[a*3]=4+level/3;palette[a*3+1]=5+level/3;palette[a*3+2]=5+level/3;}
        else if(material==2){palette[a*3]=18+level;palette[a*3+1]=20+level;palette[a*3+2]=18+level;}
        else {palette[a*3]=20+level;palette[a*3+1]=14+level;palette[a*3+2]=level/4;}
    }
    vbuf=halloc(16384,4);''')
    asm=assembly(ROOT/'COMAN/THELOOP.ASM').replace('NOJUMPS','')
    old='mov bx,fs:[si]\nadd di,ds:theloop_ysina1\nadd bx,gs:[di]'
    lookup='''add di,ds:theloop_ysina1
push dx
mov bx,di
and bx,0ff00h
mov dx,si
shr dx,8
or bx,dx
movsx bx,byte ptr fs:[bx]
pop dx'''
    count=asm.count(old);asm=asm.replace(old,lookup)
    old2=old.replace('ysina1','ysina2');count+=asm.count(old2);asm=asm.replace(old2,lookup.replace('ysina1','ysina2'))
    if count<100:raise ValueError('Terrain sample anchors changed')
    index=0
    def shade(match):
        nonlocal index
        # Atmospheric falloff; material bank is independent of height.
        light=max(4,27-index//7);index+=1
        return f'''push bx
mov bx,di
and bx,0ff00h
mov dx,si
shr dx,8
or bx,dx
mov dl,gs:[bx]
add dl,{light}
pop bx'''
    asm,n=re.subn(r'lea dx,\[bx\+\d+\]\nshr dl,1',shade,asm)
    if n<100:raise ValueError('Terrain color anchors changed')
    asm=asm.replace('short ','')
    (output/'TERRAIN.ASM').write_text(asm,encoding='cp437')
    subprocess.run([tool('jwasm'),'-q','-Cp','-omf','-FoTERRAIN.OBJ','TERRAIN.ASM'],cwd=output,check=True)
    bg=data_object((ROOT/'COMAN/COMBG.UH').read_bytes(),'combg',output/'background')
    (output/'terrain-source.json').write_text(json.dumps(provenance,indent=2)+'\n')
    return compile_c(source,output,'3DSINFLD',[ROOT/'COMAN/ASM.OBJ',output/'TERRAIN.OBJ',bg,*tables,ROOT/'DIS/DISC.OBJ'])

if __name__=='__main__':print(build(HERE/'build/full-terrain-map'))
