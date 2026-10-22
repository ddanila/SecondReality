"""Host rebuild of the plasma effects with a DIP-40 package in the cube slot."""
import re,shutil,subprocess,math
from pathlib import Path
from build import HERE,ROOT,tool


def package():
    vertices=[];faces=[]
    def box(x0,y0,z0,x1,y1,z1,color):
        base=len(vertices)
        vertices.extend([(x1,y1,z1),(x1,y0,z1),(x0,y0,z1),(x0,y1,z1),(x1,y1,z0),(x1,y0,z0),(x0,y0,z0),(x0,y1,z0)])
        for face in ((1,2,3,0),(7,6,5,4),(0,4,5,1),(1,5,6,2),(2,6,7,3),(3,7,4,0)):
            faces.append([*(v+base for v in face),0,0,0,color])
    for x,y,z in ((116,41,-22),(120,45,-16),(120,45,16),(116,41,22)):
        vertices.extend([(x,y,z),(x,-y,z),(-x,-y,z),(-x,y,z)])
    for ring in range(3):
        for i in range(4):
            j=(i+1)%4;faces.append([ring*4+i,ring*4+j,(ring+1)*4+j,(ring+1)*4+i,0,0,0,1])
    faces.extend([[3,2,1,0,0,0,0,1],[12,13,14,15,0,0,0,1]])
    box(-101,-33,22,101,33,24,0)
    box(-119,-10,22,-107,10,24,1)
    box(-111,-34,24,-105,-28,25,2)
    for side in (-1,1):
        for pin in range(20):
            x=-114+pin*12
            y0,y1=sorted((side*44,side*60));box(x,y0,-5,x+5,y1,0,2)
            y0,y1=sorted((side*57,side*62));box(x,y0,-31,x+5,y1,-2,2)
    return 'object={"U880 activity / DIP-40",'+str(len(vertices))+',{'+','.join('{'+','.join(map(str,p))+'}' for p in vertices)+'},'+str(len(faces))+',{'+','.join('{'+','.join(map(str,p))+'}' for p in faces)+'}};'


def build(output,debug=False):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    wc=ROOT.parent/'msdos/watcom'
    for name in ('TWEAK.H','PTAU.PRE'):shutil.copyfile(ROOT/'PLZPART'/name,output/name.lower())
    shutil.copyfile(ROOT/'DIS/DIS.H',output/'dis.h')
    objs=[]
    for name in ('MAIN','PLZ','PLZFILL','VECT'):
        s=(ROOT/'PLZPART'/(name+'.C')).read_text(encoding='cp437')
        s=s.replace('#include "..\\dis\\dis.h"','#include "dis.h"').replace('#include <math.h>','')
        s='#define M_PI 3.141592653589793\n#include <string.h>\n#include "dis.h"\n'+s
        s=re.sub(r'\bfar\s+(char|int|long)\b',r'\1 far',s)
        s=re.sub(r'extern\s+far\s+(\w+)\(',r'extern int far \1(',s)
        s=re.sub(r'\basm\b','_asm',s)
        s=re.sub(r'extern\s+int far (frame_count|cop_drop);',r'extern volatile int far \1;',s)
        if name=='MAIN':s='int m1,m2,m3,m4,n1,n2,n3,n4;\n'+s.replace('close_copper();','close_copper();return 0;')
        if name=='VECT':
            a=s.index('object={');b=s.index(';',a)+1;s=s[:a]+package()+s[b:]
            s=s.replace('point[256]','point[768]').replace('pg[256]','pg[512]').replace('ptodraw[256]','ptodraw[512]').replace('light_src[6]','light_src[512]').replace('lls[6]','lls[512]')
            s=s.replace('draw(15);','draw();').replace('extern int do_poly();','extern void do_poly();')
            for axis in ('x','y','z'):
                for coefficient in ('cxx','cxy','cxz','cyx','cyy','cyz','czx','czy','czz'):
                    s=s.replace(axis+'*'+coefficient,'(long)'+axis+'*'+coefficient)
            s=s.replace('c=object.pg[a].color;','c=object.pg[a].color;if(c==2)light_src[p]=56;if(c==1)light_src[p]=48;')
            s=s.replace('ptodraw[p++].p=a++;','ptodraw[p].dis=(object.point[object.pg[a].p1].zz+object.point[object.pg[a].p2].zz+object.point[object.pg[a].p3].zz+object.point[object.pg[a].p4].zz)/4;ptodraw[p++].p=a++;')
            s=s.replace('polys=p;','polys=p; for(a=1;a<p;a++){struct polygons_to_draw temp=ptodraw[a];b=a;while(b>0 && ptodraw[b-1].dis<temp.dis){ptodraw[b]=ptodraw[b-1];b--;}ptodraw[b]=temp;}')
        if name=='PLZFILL':
            for variable in ('to','from','ctau'):
                s=re.sub(r'(extern\s+(?:char|int) far\s*\*)\s*'+variable+r'\s*;',r'\1 far '+variable+';',s)
            s=re.sub(r'(extern\s+(?:int|long) far\s+)([^;()]+);',lambda m:m[1]+m[2].replace(',',',far ')+ ';',s)
            s='static int sine_seed[1524]={'+','.join(str(int(math.sin(a/1024*math.pi*4)*127)) for a in range(1524))+'};\n'+s
            s=s.replace('sin(a/1024.0*M_PI*4)*127','sine_seed[a]')
            s=s.replace('int\tkuvataus[]={FP_SEG(kuva1),FP_SEG(kuva2),FP_SEG(kuva3),FP_SEG(kuva1)};','int kuvataus[4];')
            s=s.replace('int\tdisttaus[]={FP_SEG(dist1),FP_SEG(dist1),FP_SEG(dist1),FP_SEG(dist1)};','int disttaus[4];')
            s=s.replace('initvect() {','extern int kuvataus[4],disttaus[4];\ninitvect() {')
            s=s.replace('for(a=0;a<1524;a++)','kuvataus[0]=kuvataus[3]=FP_SEG(kuva1)+(FP_OFF(kuva1)>>4);kuvataus[1]=FP_SEG(kuva2)+(FP_OFF(kuva2)>>4);kuvataus[2]=FP_SEG(kuva3)+(FP_OFF(kuva3)>>4);\n    for(a=0;a<4;a++)disttaus[a]=FP_SEG(dist1)+(FP_OFF(dist1)>>4);\n    for(a=0;a<1524;a++)')
            s=s.replace('for(y=0;y<64;y++) for(x=0;x<256;x++)','for(a=0;a<128;a++){int light=(pal[a*3]+pal[a*3+1]+pal[a*3+2])/3;pal[a*3]=light/3;pal[a*3+1]=light;pal[a*3+2]=light/2;}\n    for(y=0;y<64;y++) for(x=0;x<256;x++)',1)
            s=s.replace('kuva2[y][x]=sini[(y*4+sini[x*2])&511]/4+32+64;','kuva2[y][x]=76;')
            s=s.replace('kuva3[y][x]=sini[(y*4+sini[x*2])&511]/4+32+128;','kuva3[y][x]=180;')
            s=s.replace('for(y=0;y<64;y++) for(x=0;x<256;x++)','for(a=0;a<64;a++){pal[64*3+a*3]=pal[64*3+a*3+1]=pal[64*3+a*3+2]=a;pal[128*3+a*3]=pal[128*3+a*3+1]=pal[128*3+a*3+2]=a;}\n    for(y=0;y<64;y++) for(x=0;x<256;x++)',1)
            a=s.index('do_poly(x1,');b=s.index('clear()',a)
            s=s[:a]+(HERE/'full-scenes/plasma-fill.c').read_text()+s[b:]
        if name=='PLZ':
            # The released executable exits at curpal==4 (its checked-in C
            # says 5). The latter misses the cube cue and consumes the dots slot.
            s=s.replace('curpal==5','curpal==4')
            s=s.replace('\n\tpptr=pals;', '''for(b=0;b<5;b++)for(a=0;a<256;a++) {
                int light=(pals[b][a*3]+pals[b][a*3+1]+pals[b][a*3+2])/3;
                pals[b][a*3]=light/3;pals[b][a*3+1]=light;pals[b][a*3+2]=light/2;
            }
            pptr=pals;''')
        if debug:
            s='extern void mark(int,int,int);\n'+s
            if name=='MAIN':
                s='#include <stdio.h>\nvoid mark(int a,int b,int c){FILE *f=fopen("PLZ.LOG","at");fprintf(f,"%d %d %d\\n",a,b,c);fclose(f);}\n'+s
                s=s.replace('\tplz();\n','mark(1,0,0);plz();mark(2,0,0);\n').replace('\tvect();\n','vect();mark(3,0,0);\n')
            if name=='PLZFILL':s=s.replace('for(a=0;a<8*256;a++)','mark(79,(unsigned char)kuva3[30][100],FP_SEG(kuva3));mark(80,(unsigned char)kuva2[30][100],FP_SEG(kuva2));for(a=0;a<8*256;a++)')
            if name=='PLZFILL':
                s='static int debug_material_count;\n'+s
                s=s.replace('from=MK_FP(kuvataus[color],0);','from=MK_FP(kuvataus[color],0);if(color==2 && debug_material_count++<3)mark(83,(unsigned char)from[30*256+100],FP_SEG(from));')
            if name=='PLZ':s=s.replace('ttptr++;','ttptr++;mark(10+curpal,dis_getmframe(),cop_drop);')
            if name=='VECT':
                s=s.replace('while(dis_musplus()<13 && !dis_exit()); frame_count=0;','mark(20,dis_musplus(),0);while(dis_musplus()<13 && !dis_exit()); mark(21,dis_musplus(),0); frame_count=0;')
                s=s.replace('calculate(1);','if(frames<10)mark(22,frames,frame_count);calculate(1);if(frames<10){mark(23,polys,dis);mark(77,pal[540],fpal[540]);mark(78,object.pg[40].color,object.faces);c=0;for(a=0;a<polys;a++)if(object.pg[ptodraw[a].p].color==2)c++;mark(82,c,polys);}').replace('draw();','draw();if(frames<10)mark(24,frames,0);').replace('\t\tclear();','clear();if(frames<10)mark(25,frames,0);')
        (output/(name+'.C')).write_text(s,encoding='cp437')
        subprocess.run([tool('wcc'),'-zq','-w=0','-bt=dos','-ml','-3','-os','-s','-ecc',f'-i={wc/"h"}',f'-fo={name}.OBJ',name+'.C'],cwd=output,check=True)
        objs.append(output/(name+'.OBJ'))
    objs += [ROOT/'PLZPART'/(n+'.OBJ') for n in ('ASMYT','COPPER','INCLUDE','PLZA','TWEAK','SPLINE')]+[ROOT/'DIS/DISC.OBJ']
    args=[tool('wlink'),'format','dos','option','quiet','option','stack=8192','name','PLZPART.EXE']
    for obj in objs:args+=['file',str(obj)]
    args+=['libpath',str(wc/'lib286/dos'),'libpath',str(wc/'lib286')]
    subprocess.run(args,cwd=output,check=True)
    return output/'PLZPART.EXE'

if __name__=='__main__':print(build(HERE/'build/full-plasma'))
