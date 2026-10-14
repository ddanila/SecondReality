"""Host-build the original DOS renderer with Watcom and JWasm."""
import re
import shutil
import subprocess
from build import ROOT, expand


def assembly(path):
    source=expand(path)
    source=re.sub(r'(?im)^global\s+', 'EXTERNDEF ', source)
    source=re.sub(r'^\s*LOCALS\s*$', '', source, flags=re.M|re.I)
    lines=['OPTION NOSCOPED'];scope='global';n=0
    for line in source.splitlines():
        proc=re.match(r'(\w+)\s+PROC\b',line,re.I)
        if proc: scope=proc[1]
        line=re.sub(r'@@(\w+)',lambda m:'local_'+scope+'_'+m[1],line)
        # TASM's anonymous ENDP is not MASM syntax.
        if re.match(r'^\s*ENDP\s*$',line,re.I): line=scope+' ENDP'
        jump=re.match(r'\s*(loop|jcxz)\s+(\w+)\s*$',line,re.I)
        if jump and path.name=='ACALC.ASM':
            n+=1
            line=f'{jump[1]} jump_{n}\njmp skip_{n}\njump_{n}: jmp {jump[2]}\nskip_{n}:'
        lines.append(line)
    return '\n'.join(lines)+'\n'


def build_renderer(build,compiler,assembler,linker,watcom):
    out=build/'renderer';out.mkdir(exist_ok=True)
    for name in ('C.H','CD.H'):
        s=(ROOT/'VISU'/name).read_text(encoding='cp437').replace('#include "cd.h"','#include "CD.H"')
        s=re.sub(r'^;', '',s,flags=re.M)
        (out/name).write_text(s)
    (out/'DIS.H').write_bytes((ROOT/'DIS/DIS.H').read_bytes())
    for name in ('U2E','VISU'):
        path=ROOT/('VISU/C/U2E.C' if name=='U2E' else 'VISU/VISU.C')
        s=path.read_text(encoding='cp437')
        s=s.replace('"..\\cd.h"','"CD.H"').replace('"..\\c.h"','"C.H"').replace('"c.h"','"C.H"')
        s='#include <stdlib.h>\n#include <dos.h>\n#include "DIS.H"\nvoid vid_setswitch(int,int);\nvoid vid_clear255(void);\n'+s
        if name=='U2E':
            # Pointer arithmetic is huge-pointer aware in Watcom; avoid the
            # original compiler-specific stack-slot manipulation.
            start=s.index('\tif(size>128000)');end=s.index('\tfclose(f1);',start)
            s=s[:start]+'''    while(size>0) {
        unsigned count=size>32000L ? 32000U : (unsigned)size;
        if(fread(p,1,count,f1)!=count) exit(3);
        p+=count;size-=count;
    }
'''+s[end:]
            s=s.replace('ip=readfile(tmpname);','ip=(int huge *)readfile(tmpname);')
            s=s.replace('for(y<175;y<200;y++)','for(y=175;y<200;y++)')
            s=s.replace('if(currframe>900*2 && currframe<1100*2)','if(city && currframe>900*2 && currframe<1100*2)')
        else:
            s=s[:s.index('#define determ')]
            s=s.replace('#define GINT *(((int *)d)++)','#define GINT (d+=2, *((int *)(d-2)))')
            s=s.replace('sizeof(vlist)*o->nnum','sizeof(nlist)*o->nnum')
            # Select face order from actual transformed depth each frame.
            a=s.index('\ta=0; al=0x7fffffffL;');b=s.index('\n}',a)
            s=s[:a]+'''    {
        static int sorted[504];
        static long depth[500];
        int count=o->pl[0][0]-3,i,j,offset,*face;
        long z;
        if(count>500) exit(3);
        sorted[0]=count+3;sorted[1]=o->pl[0][1];
        for(i=0;i<count;i++) {
            offset=o->pl[0][i+2];face=(int *)(o->pd+offset);
            z=0;
            for(j=0;j<(face[0]&255);j++) z+=o->v[face[j+3]].z;
            z/=(face[0]&255);
            for(j=i;j>0 && depth[j-1]<z;j--) {
                depth[j]=depth[j-1];sorted[j+2]=sorted[j+1];
            }
            depth[j]=z;sorted[j+2]=offset;
        }
        sorted[count+2]=0;
        draw_polylist(sorted,o->pd,o->v,o->pv,o->n,o->flags);
    }'''+s[b:]
        (out/(name+'.C')).write_text(s)
        subprocess.run([compiler,'-zq','-bt=dos','-ml','-3','-os','-s','-j','-ecc',f'-i={watcom / "h"}',f'-fo={name}.OBJ',name+'.C'],cwd=out,check=True)
    objects=['U2E','VISU']
    for name in ('AMAIN','ADATA','ACALC','AVID','ADRAW','DISC'):
        src=ROOT/('DIS' if name=='DISC' else 'VISU')/(name+'.ASM')
        if name in ('AVID','ADRAW'):
            shutil.copyfile(src.with_suffix('.OBJ'),out/(name+'.OBJ'))
            objects.append(name)
            continue
        s=assembly(src)
        if name=='ACALC':
            # Projection previously truncated a 32-bit coordinate to 16 bits.
            # Bound offscreen endpoints so screen-edge differences fit signed
            # 16 bits too; the existing polygon clipper handles the remainder.
            for axis in ('x','y'):
                pattern=r'(local__calc_project(?:16)?_\d+:)\s*mov\s+es:\[di\+pvlist_'+axis+r'\],ax'
                def bounded(m):
                    label=m[1][:-1]
                    return (m[1]+' cmp eax,16000\njle '+label+'_low\nmov eax,16000\n'+
                            label+'_low: cmp eax,-16000\njge '+label+'_store\nmov eax,-16000\n'+
                            label+'_store: mov es:[di+pvlist_'+axis+'],ax')
                s=re.sub(pattern,bounded,s)
        (out/(name+'.ASM')).write_text(s,encoding='cp437')
        subprocess.run([assembler,'-q','-Cp','-omf','-Fo'+name+'.OBJ',name+'.ASM'],cwd=out,check=True)
        objects.append(name)
    cmd=[linker,'format','dos','option','quiet','option','stack=4096','name',str(build/'dos/U2E.EXE')]
    for name in objects: cmd+=['file',name+'.OBJ']
    cmd+=['libpath',str(watcom/'lib286/dos'),'library','clibl']
    subprocess.run(cmd,cwd=out,check=True)
