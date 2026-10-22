#!/usr/bin/env python3
"""Host rebuild of ALKU with released font art and editable Robotron cards."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import numpy as np
from PIL import Image
from build import HERE,ROOT,tool

# Preserve the atlas order: the narrow punctuation after '=' is an apostrophe.
ORDER="ABCDEFGHIJKLMNOPQRSTUVWXabcdefghijklmnopqrstuvwxyz0123456789!?,.:&()+-*='[]"
EXTRA='äöüÄÖÜß/'
CARDS=[['Robotron','1715','Made in Sömmerda'],['East Germany','First shown in 1984']]
CREDITS=[['Graphics / Music','Marvel / Pixel','Purple Motion','Skaven'],
         ['Code / Design','Psi / Trug','Wildfire / Abyss','Gore'],
         ['Original Computer','Robotron','Sömmerda'],
         ['Development','and Production','BWS Team']]


def encode(text):
    return bytes(128+EXTRA.index(c) if c in EXTRA else ord(c) for c in text)


def literal(text):
    return '"'+''.join('\\%03o'%b if b>=128 else chr(b) for b in encode(text))+'"'


def released_font(executable):
    b=Path(executable).read_bytes()
    seed=bytes(map(int,re.findall(r'\d+',(ROOT/'ALKU/FONA.INC').read_text())[:512]))
    offset=b.find(seed)
    if offset<0:raise ValueError('Expected released font not found; decompress ALKU first')
    raw=b[offset:offset+48000]
    if len(raw)!=48000 or max(raw)>3:raise ValueError('Invalid released font bounds')
    font=np.frombuffer(raw,dtype=np.uint8).reshape(32,1500)
    occupied=np.any(font,axis=0); bounds=[];x=0
    while x<1500:
        if not occupied[x]:x+=1;continue
        start=x
        while x<1500 and occupied[x]:x+=1
        bounds.append((start,x))
    if len(bounds)!=len(ORDER):raise ValueError(f'Font mapping mismatch {len(bounds)} != {len(ORDER)}')
    glyphs={c:font[:,a:b].copy() for c,(a,b) in zip(ORDER,bounds)}
    glyphs[' ']=np.zeros((32,16),dtype=np.uint8)
    for c in EXTRA:
        base=c.translate(str.maketrans('äöüÄÖÜ','aouAOU'))
        if c=='/':
            g=np.zeros((32,9),dtype=np.uint8)
            for y in range(14):
                x=7-y//2;g[y,x:x+2]=3
        elif c=='ß':
            # Hand-built composite from the original f and s strokes.
            f=glyphs['f'];s=glyphs['s'];g=np.zeros((32,max(f.shape[1],s.shape[1])+3),dtype=np.uint8)
            g[:,:f.shape[1]]=f
            g[17:,3:3+s.shape[1]]=s[17:]
        else:
            g=glyphs[base].copy()
            if c.isupper():
                g[:]=0;g[6:]=np.asarray(Image.fromarray(glyphs[base]).resize((g.shape[1],26),Image.Resampling.NEAREST))
            for x in (g.shape[1]//3,2*g.shape[1]//3):g[0:2,max(0,x-1):x+2]=3
        glyphs[c]=g
    return raw,glyphs


def build(output, released, robotron=True):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    raw,glyphs=released_font(released)
    # Preserve released Dolby glyphs byte-for-byte; extra glyphs live separately.
    asm='.model large\n.data\n'
    for segment,filename,label in [('horizon0','HOI.IN0','hzpic'),('horizon1','HOI.IN1',None)]:
        asm+=f'{segment} segment byte public "FAR_DATA"\n'
        if label:asm+='public _'+label+'\n_'+label+' label byte\n'
        asm+=(ROOT/'ALKU'/filename).read_text(encoding='cp437')+'\n'+segment+' ends\n'
    asm+='fontdata segment para public "FAR_DATA"\npublic _font\n_font label byte\n'
    asm+='\n'.join('db '+','.join(map(str,raw[i:i+32])) for i in range(0,len(raw),32))
    asm+='\nfontdata ends\nend\n'
    (output/'ART.ASM').write_text(asm,encoding='cp437')
    extra=np.zeros((len(EXTRA),32,32),dtype=np.uint8)
    for i,c in enumerate(EXTRA):extra[i,:,:glyphs[c].shape[1]]=glyphs[c]*64
    header='static unsigned char far extra_font[%d][32][32]={'%len(EXTRA)+','.join('{'+','.join('{'+','.join(map(str,row))+'}' for row in g)+'}' for g in extra)+'};\n'
    header+='static int extra_width[%d]={'%len(EXTRA)+','.join(str(glyphs[c].shape[1]) for c in EXTRA)+'};\n'
    header+='static int fontpixel(int y,int x) { if(x>=1756)return 0;if(x<1500)return font[y][x];return extra_font[(x-1500)/32][y][(x-1500)%32]; }\n'
    (output/'EXTRA.H').write_text(header)
    source=(ROOT/'ALKU/MAIN.C').read_text(encoding='cp437')
    source=source.replace('#include "h:\\u2\\dis\\dis.h"','#include "dis.h"\n#include <string.h>\n#define outport outpw\nint dis_sync(void);')
    source=re.sub(r'\basm\s+','_asm ',source)
    source=re.sub(r'\bfar\s+(int|char)\b',r'\1 far',source)
    source=source.replace('extern\tint far frame_count','extern volatile int far frame_count')
    source=source.replace('extern  int far cop_dofade','extern volatile int far cop_dofade')
    source=source.replace('extern char far font[31][1500];','extern char far font[32][1500];\n#include "EXTRA.H"')
    source=re.sub(r'char\s+\*fonaorder=.*?;', 'unsigned char *fonaorder="'+ORDER+'";',source)
    source=source.replace('"\u00c5"','"["').replace('"\u00d6"','"]"')
    # Both original final glyph codes are converted explicitly, not by Unicode assumptions.
    source=source.replace('prtc(160,160,"'+bytes([0x8f]).decode('cp437')+'");','prtc(160,160,"[");')
    source=source.replace('prtc(160,179,"'+bytes([0x99]).decode('cp437')+'");','prtc(160,179,"]");')
    for expr in ('*txt','*t++','*t'):
        source=source.replace('fonaw['+expr+']','fonaw[(unsigned char)('+expr+')]')
        source=source.replace('fonap['+expr+']','fonap[(unsigned char)('+expr+')]')
    source=source.replace('font[y2-y][sx]','fontpixel(y2-y,sx)')
    source=source.replace('font[y][fonap[(unsigned char)(*t)]+x]','fontpixel(y,fonap[(unsigned char)(*t)]+x)')
    source=source.replace('fonap[32]=1500-20;','for(a=0;a<8;a++){fonap[128+a]=1500+a*32;fonaw[128+a]=extra_width[a];}\n\tfonap[32]=1756;')
    # The original clear used a 320-byte stride, but tbuf has 352-byte rows.
    source=source.replace('memset(tbuf,0,186*320);','_fmemset(tbuf,0,sizeof(tbuf));')
    # Empty final page must also retire the previous XOR scrolling program.
    # Near the panorama end fmaketext is skipped, so old deltas otherwise
    # redraw the last credit after ffonapois has erased it.
    source=source.replace('case 4:\n', 'case 4:\n                for(b=0;b<8;b++) dtau[b]=-1;\n')
    if robotron:
        for old,new in [('"A"',literal(CARDS[0][0])),('"Future Crew"',literal(CARDS[0][1])),('"Production"',literal(CARDS[0][2])),('"First Presented"',literal(CARDS[1][0])),('"at Assembly 93"',literal(CARDS[1][1]))]:source=source.replace(old,new)
        begin=source.index('\t\t\tcase 0:');end=source.index('\t\t\tcase 4:',begin)
        cases=''
        for i,lines in enumerate(CREDITS):
            cases+=f'\t\t\tcase {i}:\n'
            ys=[30,70,110,148] if len(lines)==4 else [50,90,130]
            for y,line in zip(ys,lines):cases+=f'                '+('addtext' if i==0 else 'faddtext')+f'(160,{y},{literal(line)});\n'
            cases+='                ffonapois();\n                break;\n'
        source=source[:begin]+cases+source[end:]
    source = 'unsigned music_position(void);\n#pragma aux music_position = "mov bx,6" "int 0fch" "shl cx,6" "or bx,cx" "mov ax,bx" value [ax] modify [bx cx dx]\n' + source
    source=source.replace('close_copper();\n\t}', 'close_copper();\n    while(music_position()<10*64 && !dis_exit()) dis_waitb();\n    return 0;\n\t}',1)
    (output/'MAIN.C').write_text(source+'\n',encoding='cp437')
    for path in (ROOT/'ALKU/TWEAK.H',ROOT/'DIS/DIS.H'):shutil.copyfile(path,output/path.name.lower())
    widths={s:sum(glyphs[c].shape[1]+2 for c in s) for card in CARDS+CREDITS for s in card}
    # Retain native glyph sizes; fail rather than clipping or extending timing.
    if max(widths.values())>318:raise ValueError('Opening line exceeds screen: '+str(widths))
    wc=ROOT.parent/'msdos/watcom'
    subprocess.run([tool('wcc'),'-zq','-w=0','-bt=dos','-ml','-3','-os','-s','-ecc',f'-i={wc/"h"}','-fo=MAIN.OBJ','MAIN.C'],cwd=output,check=True)
    subprocess.run([tool('jwasm'),'-q','-Cp','-omf','-FoART.OBJ','ART.ASM'],cwd=output,check=True)
    args=[tool('wlink'),'format','dos','option','quiet','option','stack=8192','option','map=ALKU.MAP','name','ALKU.EXE','file','MAIN.OBJ','file','ART.OBJ']
    for obj in ('TWEAK','COPPER','ASMYT'):args+=['file',str(ROOT/'ALKU'/(obj+'.OBJ'))]
    args+=['file',str(ROOT/'DIS/DISC.OBJ'),'libpath',str(wc/'lib286/dos'),'libpath',str(wc/'lib286')]
    subprocess.run(args,cwd=output,check=True)
    (output/'opening.json').write_text(json.dumps({'cards':CARDS,'credits':CREDITS,'widths':widths,'extra_encoding':{c:128+i for i,c in enumerate(EXTRA)},'dolby':'unchanged released glyphs and calls','robotron':robotron},ensure_ascii=False,indent=2)+'\n')
    return output/'ALKU.EXE'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--released',type=Path,required=True);p.add_argument('--output',type=Path,default=HERE/'build/full-opening');p.add_argument('--original-text',action='store_true');a=p.parse_args();print(build(a.output,a.released,not a.original_text))
