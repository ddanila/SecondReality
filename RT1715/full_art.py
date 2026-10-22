#!/usr/bin/env python3
"""Convert review artwork to original VGA assets and host-build picture parts."""
import json
from pathlib import Path
import re
import shutil
import struct
import subprocess
import numpy as np
from PIL import Image
from build import HERE,ROOT,tool

ART=HERE/'assets/full-demo/art'


def packed_picture(image, colors=127):
    # Slot zero is the background in JP and PANICEND. Quantizers do not
    # guarantee that convention; reserve it explicitly and shift all colors.
    quantized=image.convert('RGB').quantize(colors=colors-1,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    pixels=np.asarray(quantized).astype(np.uint8)+1
    rgb=np.asarray(image.convert('RGB'))
    pixels[np.max(rgb,axis=2)==0]=0
    im=Image.fromarray(pixels).convert('P')
    rgb_palette=([0,0,0]+quantized.getpalette()[:3*(colors-1)])
    im.putpalette(rgb_palette+[0]*(768-len(rgb_palette)))
    palette=bytes(v//4 for v in im.getpalette()[:768])
    rows=[]
    for row in np.asarray(im):
        buf=bytearray();i=0
        while i<len(row):
            value=int(row[i]);end=i+1
            while end<len(row) and row[end]==value and end-i<127:end+=1
            count=end-i
            if count>1 or value>=128:buf.extend((128+count,value))
            else:buf.append(value)
            i=end
        rows.append(struct.pack('<H',len(buf))+buf)
    header=struct.pack('<5H',0,image.width,image.height,256,49).ljust(16,b'\0')
    return header+palette+b''.join(rows),im


def build_picture(name,output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    image=Image.open(ART/(name+'-draft.png')).convert('RGB')
    if name=='unicorn':
        panel=image.resize((184,400),Image.Resampling.LANCZOS)
        image=Image.new('RGB',(320,400));image.paste(panel,(70,0))
    else:image=image.resize((320,400),Image.Resampling.LANCZOS)
    # Normalize far pointers like TECHNO so detailed artwork may cross 64 KiB.
    for colors in (63,47,31,23,15):
        data,preview=packed_picture(image,colors)
        if len(data)<128000:break
    else:raise ValueError('Picture does not fit original reader')
    preview.convert('RGB').resize((640,480)).save(output/(name+'-vga.png'))
    (output/(name+'.UP')).write_bytes(data)
    folder='BEG' if name=='title' else 'JPLOGO';filename='BEG.C' if name=='title' else 'JP.C'
    source=(ROOT/folder/filename).read_text(encoding='cp437')
    source=source.replace('#include "..\\dis\\dis.h"','#include "dis.h"\n#include <string.h>\n#include <conio.h>\n#include <dos.h>')
    if name=='unicorn':
        begin=source.index('int\tcalc(');end=source.index('void\tdoit(',begin)
        source=source[:begin]+'int calc(int y,int c) {return (int)(((long)y-400+c)*400/c);}\n\n'+source[end:]
    source=re.sub(r'\basm\b','_asm',source)
    if name=='title':
        source=source.replace('//inittwk();','')
        source=source.replace('int\ta,b,c,y;','int\ta,b,c,y; int start;')
        source=source.replace('dis_partstart();','dis_partstart();\n    start=0; dis_waitb();\n    _asm mov ax,13h\n    _asm int 10h\n    inittwk();')
        source=source.replace('for(a=0;a<32;a++) dis_waitb();','')
        source=source.replace('for(c=0;c<=128;c++)','while(start<31) start+=dis_waitb();\n    for(c=0;c<=128;c++)')
        source=source.rstrip().removesuffix('}')+'return 0;\n}\n'
    (output/'MAIN.C').write_text(source,encoding='cp437')
    (output/'readp.c').write_text(r"""
/* Huge source arithmetic crosses the 64 KiB asset boundary safely. */
void readp(unsigned char far *dest,int row,unsigned char huge *src) {
    unsigned width, height, colors, offset, bytes, count, value;
    unsigned char huge *end;
    height=*(unsigned huge *)(src+4);
    colors=*(unsigned huge *)(src+6);
    offset=*(unsigned huge *)(src+8);
    if(row==-1) { src+=16; for(width=0;width<colors*3;width++) *dest++=*src++; return; }
    if(row<0 || row>=height) return;
    src+=(unsigned long)offset*16;
    while(row--) { bytes=*(unsigned huge *)src; src+=(unsigned long)bytes+2; }
    bytes=*(unsigned huge *)src; src+=2; end=src+bytes;
    while(src<end) {
        value=*src++; count=1;
        if(value&128) { count=value&127; value=*src++; }
        while(count--) *dest++=value;
    }
}
""")
    shutil.copyfile(ROOT/'DIS/DIS.H',output/'dis.h')
    assembly='.model large\n'
    for n,start in enumerate(range(0,len(data),64000)):
        assembly+=f'art{n} segment para public "FAR_DATA"\n'
        if n==0:assembly+='public _pic\n_pic label byte\n'
        chunk=data[start:start+64000]
        assembly+='\n'.join('db '+','.join(map(str,chunk[i:i+32])) for i in range(0,len(chunk),32))+f'\nart{n} ends\n'
    assembly+='end\n'
    (output/'ART.ASM').write_text(assembly)
    wc=ROOT.parent/'msdos/watcom'
    subprocess.run([tool('wcc'),'-zq','-w=0','-bt=dos','-ml','-3','-os','-s','-ecc',f'-i={wc/"h"}','-fo=MAIN.OBJ','MAIN.C'],cwd=output,check=True)
    subprocess.run([tool('jwasm'),'-q','-Cp','-omf','-FoART.OBJ','ART.ASM'],cwd=output,check=True)
    exe='BEGLOGO.EXE' if name=='title' else 'JPLOGO.EXE'
    subprocess.run([tool('wlink'),'format','dos','option','quiet','option','stack=8192','name',exe,'file','MAIN.OBJ','file','ART.OBJ','file',str(ROOT/folder/'ASM.OBJ'),'file',str(ROOT/'DIS/DISC.OBJ'),'libpath',str(wc/'lib286/dos'),'libpath',str(wc/'lib286')],cwd=output,check=True)
    return output/exe


def monster(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    im=Image.open(ART/'monster-draft.png').convert('RGB').resize((320,200),Image.Resampling.LANCZOS).resize((320,400),Image.Resampling.NEAREST)
    # TECHNO already loads this external picture, and normalizes segment offsets.
    for colors in (127,95,63,47,31,23,15):
        data,p=packed_picture(im,colors)
        if len(data)<=80000:break
    else:raise ValueError('Monster exceeds original loader capacity')
    (output/'TROLL.UP').write_bytes(data)
    p.convert('RGB').resize((640,480)).save(output/'monster-vga.png')
    return output/'TROLL.UP'

if __name__=='__main__':
    out=HERE/'build/full-art-built'
    for name in ('title','unicorn'):print(build_picture(name,out/name))
    print(monster(out/'monster'))
