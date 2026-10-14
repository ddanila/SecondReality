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
    shutil.copyfile(ROOT/'RT1715/fast.h',out/'fast.h')
    shutil.copyfile(ROOT/'RT1715/lighting.h',out/'lighting.h')
    from music import flight_header
    (out/'MUSIC.H').write_text(flight_header(ROOT/'MAIN/MUSIC0.S3M'))
    for name in ('C.H','CD.H'):
        s=(ROOT/'VISU'/name).read_text(encoding='cp437').replace('#include "cd.h"','#include "CD.H"')
        s=re.sub(r'^;', '',s,flags=re.M)
        # ASM data lives outside Watcom DGROUP; C must use segment relocations.
        s=re.sub(r'(extern\s+(?:int|long))\s+(vramseg|proj\w+|rows)\b',r'\1 far \2',s)
        (out/name).write_text(s)
    (out/'DIS.H').write_bytes((ROOT/'DIS/DIS.H').read_bytes())
    for name in ('U2E','VISU'):
        path=ROOT/('VISU/C/U2E.C' if name=='U2E' else 'VISU/VISU.C')
        s=path.read_text(encoding='cp437')
        s=s.replace('"..\\cd.h"','"CD.H"').replace('"..\\c.h"','"C.H"').replace('"c.h"','"C.H"')
        s='#include "fast.h"\nvoid rt_depth_end(void);\nvoid rt_begin(void);\nvoid rt_flush(void);\n#include <stdlib.h>\n#include <dos.h>\n#include "DIS.H"\nvoid vid_setswitch(int,int);\nvoid vid_clear255(void);\n'+s
        if name=='U2E':
            # Pointer arithmetic is huge-pointer aware in Watcom; avoid the
            # original compiler-specific stack-slot manipulation.
            start=s.index('\tif(size>128000)');end=s.index('\tfclose(f1);',start)
            s=s[:start]+'''    while(size>0) {
        unsigned count=size>32000L ? 32000U : (unsigned)size;
        /* fread takes a far pointer: never let a chunk cross its 64K window. */
        p=(char huge *)MK_FP(FP_SEG(p)+(FP_OFF(p)>>4),FP_OFF(p)&15);
        if(fread(p,1,count,f1)!=count) exit(3);
        p+=count;size-=count;
    }
'''+s[end:]
            s=s.replace('unsigned char huge *sp;', '''unsigned char huge *sp;
static unsigned char huge *rt_buffer;
static unsigned rt_loaded;
static FILE *rt_anim;
static void rt_refill(void) {
    unsigned used=(unsigned)(sp-rt_buffer),left=rt_loaded-used;
    if(left<4096U && !feof(rt_anim)) {
        rt_copy386(rt_buffer,sp,left);
        rt_loaded=left+fread(rt_buffer+left,1,8192U-left,rt_anim);
        if(ferror(rt_anim)) exit(3);
        sp=rt_buffer;
    }
}''')
            a=s.index('\tsprintf(tmpname,"%s.0AA",scene);')
            b=s.index('\n\tresetscene();',a)
            s=s[:a]+'''
    sprintf(tmpname,"%s.0AB",scene);
    rt_anim=fopen(tmpname,"rb");
    if(!rt_anim) exit(3);
    rt_buffer=(unsigned char huge *)getmem(8192L);
    rt_loaded=fread(rt_buffer,1,8192U,rt_anim);
    scenelist[0].data=(char *)rt_buffer;scl=1;
'''+s[b:]
            s=s.replace('// parse animation stream for 1 frame','rt_refill();\n\t\t// parse animation stream for 1 frame')
            # Let DOS allocate scene geometry in UMBs before conventional RAM.
            # Unsupported DOS functions leave the default strategy in place.
            s=s.replace('dis_partstart();', r'''dis_partstart();
    _asm {
        mov ax,5800h
        int 21h
        mov rt_dos_strategy,ax
        mov ax,5802h
        int 21h
        xor ah,ah
        mov rt_dos_link,ax
    }
    _asm {
        mov ax,5803h
        mov bx,1
        int 21h
    }
    _asm {
        mov ax,5801h
        mov bx,80h
        int 21h
    }
''')
            # Read tracker position atomically; the VGA counter only interpolates
            # within a row. This also catches up after a slow rendering frame.
            s=s.replace('main(int argc,char *argv[])', r'''
#include "MUSIC.H"
unsigned rt_position(void);
#pragma aux rt_position = "mov bx,6" "int 0fch" "shl cx,6" "or bx,cx" "mov ax,bx" value [ax] modify [bx cx dx]
static unsigned rt_last=65535U, rt_stamp;
static FILE *rt_trace;
static int rt_cue=0;
static unsigned rt_dos_strategy,rt_dos_link;
static int rt_music_frame(void) {
    unsigned pos=rt_position(), order=pos>>6, row=pos&63;
    long frame;
    if(pos!=rt_last) { rt_last=pos; rt_stamp=syncframe; }
    if(order<19) return 0;
    if(order>26) return 4200;
    frame=(long)rt_row_cs[order-19][row]*70L/100L;
    frame+=(unsigned)(syncframe-rt_stamp);
    return (int)frame;
}
main(int argc,char *argv[])''')
            s=s.replace('coppercnt=0;\n\tsyncframe=0;', 'coppercnt=0;\n\tcopperdelay=1;\n\trt_trace=fopen("FLIGHT.LOG","wt");\n\tsyncframe=0;')
            s=s.replace('a=(syncframe-currframe);', r'''a=(rt_music_frame()-currframe);
        if(rt_trace && ((rt_cue==0 && currframe>=3186) ||
                       (rt_cue==1 && currframe>=3344))) {
            unsigned pos=rt_position();
            fprintf(rt_trace,"%s frame=%d order=%u row=%u\n",
                    rt_cue==0 ? "OVERVIEW" : "SWOOSH",currframe,pos>>6,pos&63);
            fflush(rt_trace); rt_cue++;
        }''')
            # Preserve the overview framebuffer across loading CRED.EXE.
            s=s.replace('dis_setcopper(2,NULL);', r'''dis_setcopper(2,NULL);
    fclose(rt_anim);
    rt_depth_end();
    if(rt_trace) {
        unsigned pos=rt_position();
        fprintf(rt_trace,"END order=%u row=%u frame=%d\n",pos>>6,pos&63,currframe);
        fclose(rt_trace);
    }
    _asm {
        mov ax,5801h
        mov bx,rt_dos_strategy
        int 21h
        mov ax,5803h
        mov bx,rt_dos_link
        int 21h
    }
    return 0;''')
            s=s.replace('ip=readfile(tmpname);','ip=(int huge *)readfile(tmpname);')
            s=s.replace('dis>co[order[b]].dist','dis<co[order[b]].dist')
            s=s.replace('// Draw\n', '// Draw\n\t\trt_begin();\n')
            s=s.replace('// **** Drawing completed **** //','rt_flush();\n\t\t// **** Drawing completed **** //')
            s=s.replace('for(y<175;y<200;y++)','for(y=175;y<200;y++)')
            s=s.replace('if(currframe>900*2 && currframe<1100*2)','if(city && currframe>900*2 && currframe<1100*2)')
        else:
            s=s[:s.index('#define determ')]
            s=s.replace('#define GINT *(((int *)d)++)','#define GINT (d+=2, *((int *)(d-2)))')
            s=s.replace('sizeof(vlist)*o->nnum','sizeof(nlist)*o->nnum')
            s=s.replace('o->v=getmem(sizeof(vlist)*o->vnum);','o->v=NULL;')
            s=s.replace('o->pv=getmem(sizeof(pvlist)*o->vnum);','o->pv=NULL;')
            s=s.replace('o->n=getmem(sizeof(nlist)*o->nnum);','o->n=NULL;')
            a=s.index('void\tvis_drawobject(')
            s=s[:a]+"void rt_queue(object *o);\nvoid vis_drawobject(object *o) { rt_queue(o); }\n"
        (out/(name+'.C')).write_text(s)
        subprocess.run([compiler,'-zq','-bt=dos','-ml','-3','-os','-s','-j','-ecc',f'-i={watcom / "h"}',f'-fo={name}.OBJ',name+'.C'],cwd=out,check=True)
    shutil.copyfile(ROOT/'RT1715/depth.h',out/'depth.h')
    shutil.copyfile(ROOT/'RT1715/fast.asm',out/'FAST.ASM')
    subprocess.run([assembler,'-q','-Cp','-omf','-FlFAST.LST','-FoFAST.OBJ','FAST.ASM'],cwd=out,check=True)
    shutil.copyfile(ROOT/'RT1715/depth.c',out/'DEPTH.C')
    subprocess.run([compiler,'-zq','-bt=dos','-ml','-3','-ot','-s','-j','-ecc',
                    f'-i={watcom / "h"}','-fo=DEPTH.OBJ','DEPTH.C'],cwd=out,check=True)
    shutil.copyfile(ROOT/'RT1715/painter.c',out/'PAINTER.C')
    subprocess.run([compiler,'-zq','-bt=dos','-ml','-3','-os','-s','-j','-ecc',
                    f'-i={watcom / "h"}','-fo=PAINTER.OBJ','PAINTER.C'],cwd=out,check=True)
    objects=['U2E','VISU','PAINTER','DEPTH','FAST']
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
    cmd=[linker,'format','dos','option','quiet','option','stack=4096','option','map=U2E.MAP','name',str(build/'dos/U2E.EXE')]
    for name in objects: cmd+=['file',name+'.OBJ']
    cmd+=['libpath',str(watcom/'lib286/dos'),'library','clibl']
    subprocess.run(cmd,cwd=out,check=True)
