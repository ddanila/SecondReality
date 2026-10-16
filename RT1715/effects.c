/* Robotron reinterpretations of the Second Reality effect vocabulary.
 * Live 320x200 indexed rendering, with host-generated source imagery/tables.
 * Original algorithm references and editorial decisions: EXPANSION-PLAN.txt.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#ifndef FX_HOST
#include <dos.h>
#include <i86.h>
#include <conio.h>
#endif
#ifndef FX_POST
#define FX_POST 0
#endif
#define W 320
#define H 200
#define PI 3.14159265358979323846
static unsigned char frame[64000],palette[768],font[95*96];
static unsigned char *pictures;
static unsigned char crt_picture[256000],crt_mask[256000];
static float crt_focus[2];
static unsigned char backdrop[3][64000],detailpic[3][90*62];
static int sine[1024];
static short *points;
static unsigned point_count;
static float boxes[512][6],focus[6];
static double scene_gain=1;
static unsigned kinds[512],box_count;
static const char *names[]={"IDENTITY","LENS","TUNNEL","GLENZ","TECHNO","PLASMA","TERRAIN","MIRROR","MOUNTAIN","JELLY","SCREEN_IN","SCREEN_OUT"};
typedef struct { short v[9]; unsigned char color,group; } meshtri;
static const unsigned char material_rgb[8][3]={{201,193,167},{187,194,194},{56,116,91},{30,34,35},{145,181,197},{221,220,203},{182,65,57},{120,95,65}};
static unsigned char boot_screen[640*288];
static meshtri *mesh;static unsigned mesh_count;static float entry_camera[6],depthbuffer[64000];
static unsigned *visibility[12][512],vis_count[12][512],vis_frames[12],visible_ids[64000];
static unsigned char *visible_flags;
static int bake_visibility;
static FILE *trace;
static void fail(const char *s) { if(trace) { fprintf(trace,"ERROR %s\n",s);fclose(trace); } fprintf(stderr,"FX: %s\n",s);exit(3); }
static unsigned read32(FILE *f) { unsigned char b[4];if(fread(b,1,4,f)!=4)fail("truncated table");return (unsigned)b[0]|((unsigned)b[1]<<8)|((unsigned)b[2]<<16)|((unsigned)b[3]<<24); }
static void load_bytes(const char *name,void *dest,unsigned size) { FILE *f=fopen(name,"rb");if(!f)fail(name);if(fread(dest,1,size,f)!=size || fgetc(f)!=EOF)fail("asset length");fclose(f); }
static double fx_min(double a,double b) { return a<b?a:b; }
static double fx_max(double a,double b) { return a>b?a:b; }
static double clamp(double x,double a,double b) { return x<a?a:(x>b?b:x); }
static double ease(double x) { x=clamp(x,0,1);return x*x*(3-2*x); }
static void pixel(int x,int y,int c) { if(x>=0&&x<W&&y>=0&&y<H)frame[y*W+x]=(unsigned char)c; }
static void line(int x0,int y0,int x1,int y1,int c) {
    int dx=abs(x1-x0),sx=x0<x1?1:-1,dy=-abs(y1-y0),sy=y0<y1?1:-1,err=dx+dy,e;
    if(abs(x0)>4000||abs(y0)>4000||abs(x1)>4000||abs(y1)>4000)return;
    for(;;) { pixel(x0,y0,c);if(x0==x1&&y0==y1)break;e=2*err;if(e>=dy){err+=dy;x0+=sx;}if(e<=dx){err+=dx;y0+=sy;} }
}
static void text(int x,int y,const char *s,int color) {
    int i,j,c;while(*s){c=(unsigned char)*s++-32;if(c>=0&&c<95)for(j=0;j<12;j++)for(i=0;i<8;i++)if(font[c*96+j*8+i])pixel(x+i,y+j,color);x+=8;}
}
static void centered(int y,const char *s,int c) { text((320-(int)strlen(s)*8)/2,y,s,c); }
static unsigned sample(int image,double x,double y) {
    int ix=(int)x,iy=(int)y;unsigned a,b,c,d;
    if(ix<0||iy<0||ix>=639||iy>=399)return 0;
    a=pictures[image*256000+iy*640+ix];b=pictures[image*256000+iy*640+ix+1];
    c=pictures[image*256000+(iy+1)*640+ix];d=pictures[image*256000+(iy+1)*640+ix+1];
    return (unsigned)((a*(1-(x-ix))+b*(x-ix))*(1-(y-iy))+(c*(1-(x-ix))+d*(x-ix))*(y-iy));
}
static void disk(int x,int y,int radius,int col) { int a,b;for(b=-radius;b<=radius;b++)for(a=-radius;a<=radius;a++)if(a*a+b*b<=radius*radius)pixel(x+a,y+b,col); }
static void picture(int image,int x0,int y0,int width,int height) {
    int x,y;for(y=0;y<height;y++)for(x=0;x<width;x++)pixel(x+x0,y+y0,sample(image,x*639.0/width,y*399.0/height));
}
static void identity(double t,double length) {
    unsigned i;double arrive=ease(t/3.6),depart=ease((t-length+1.3)/1.3);int x,y;
    for(i=0;i<point_count;i++) {
        double a=i*2.399963+(.9*t)*(1-arrive),r=220*(1-arrive),z=1+depart*5;
        x=(int)(160+(points[i*2]-160)*z+r*cos(a));
        y=(int)(100+(points[i*2+1]-100)*z+r*.65*sin(a));
        pixel(x,y,150+(i%30));pixel(x+1,y,150+(i%30));if(arrive<.95)pixel(x,y+1,90);
    }
    if(t>3.7&&t<length-1.0)centered(169,"A JOURNEY THROUGH THE MACHINE",136);
}
static void lens(double t,double length) {
    int x,y,detail=(int)clamp(t*3/length,0,2);
    double local=t*3/length-detail,angle=local*PI*1.5;
    double sx=clamp(focus[detail*2]+50*sin(angle)-35*(1-ease(local*4)),100,540);
    double sy=clamp(focus[detail*2+1]+32*sin(angle*.8),90,310);
    double cx=sx*.5,cy=24+sy*151/400;
    scene_gain=ease(local*length/3/.22)*ease((1-local)*length/3/.22);
    memcpy(frame,backdrop[detail],64000);
    for(y=25;y<176;y++)for(x=0;x<320;x++) {
        double dx=x-cx,dy=y-cy,r=dx*dx+dy*dy*1.44;
        /* Magnify the point directly underneath the moving lens. */
        if(r<43*43)frame[y*320+x]=(unsigned char)sample(detail,sx+dx*.70,sy+dy*.93);
        else if(r<45*45)frame[y*320+x]=160;
    }
    line((int)cx-5,(int)cy,(int)cx+5,(int)cy,165);
    line((int)cx,(int)cy-4,(int)cx,(int)cy+4,165);
    centered(181,detail==0?"U880 / INSTRUCTION PROCESSING":detail==1?"MAIN RAM / WORKING STORAGE":"VIDEO RAM / CHARACTER STORAGE",172);
}
static void tunnel(double t,double length) {
    int ring,k;double speed=70+45*ease(t/length),cx=160+35*sin(t*.55),cy=99+20*sin(t*.7);
    for(ring=35;ring>=0;ring--) {
        double z=fmod(ring*23-t*speed+100000,820)+18,r=5600/z;
        for(k=0;k<48;k++) { double a=k*PI/24+t*.13;int x=(int)(cx+r*cos(a)),y=(int)(cy+r*.72*sin(a));
            if(y>22&&y<176)disk(x,y,z<120?1:0,128+(int)(50*(1-z/850)));
        }
    }
    centered(181,t<length*.33?"KEYBOARD > PROCESSOR":t<length*.66?"PROCESSOR > MEMORY":"MEMORY > DISPLAY",172);
}
static void triangle(int x0,int y0,int x1,int y1,int x2,int y2,int color,int alpha) {
    int x,y,a,b,c,ar,br,cr,ax,ay,bx,by,cx,cy,sign;
    int minx=(int)clamp(fx_min(x0,fx_min(x1,x2)),0,319),maxx=(int)clamp(fx_max(x0,fx_max(x1,x2)),0,319);
    int miny=(int)clamp(fx_min(y0,fx_min(y1,y2)),22,177),maxy=(int)clamp(fx_max(y0,fx_max(y1,y2)),22,177);
    sign=((x1-x0)*(y2-y0)-(y1-y0)*(x2-x0))<0?-1:1;
    ax=-(y1-y0)*sign;ay=(x1-x0)*sign;bx=-(y2-y1)*sign;by=(x2-x1)*sign;cx=-(y0-y2)*sign;cy=(x0-x2)*sign;
    ar=((x1-x0)*(miny-y0)-(y1-y0)*(minx-x0))*sign;
    br=((x2-x1)*(miny-y1)-(y2-y1)*(minx-x1))*sign;
    cr=((x0-x2)*(miny-y2)-(y0-y2)*(minx-x2))*sign;
    for(y=miny;y<=maxy;y++) {
        a=ar;b=br;c=cr;
        for(x=minx;x<=maxx;x++) {
            if((a|b|c)>=0)frame[y*320+x]=(unsigned char)(alpha?(frame[y*320+x]*3+color)/4:color);
            a+=ax;b+=bx;c+=cx;
        }
        ar+=ay;br+=by;cr+=cy;
    }
}

/* Perspective source geometry with per-pixel depth: no envelope boxes. */
static void source_mesh(double t,double length,int mode) {
    unsigned i,vi,vn=mesh_count,*selected=0;int x,y,k;double p=ease(t/length),eye[3],target[3],f[3],r[3],d[3],norm;
    double split;unsigned scene=mode==0?3:(mode==1?10:11);
    if(vis_frames[scene]&&!bake_visibility) {
        unsigned at=(unsigned)clamp(floor(t/length*(vis_frames[scene]-1)+.5),0,vis_frames[scene]-1);
        t=length*at/(vis_frames[scene]-1);p=ease(t/length);
        selected=visibility[scene][at];vn=vis_count[scene][at];
    }
    split=mode==0?65*sin(PI*p):0;
    if(mode==0) {
        double a=-.6+p*.7;eye[0]=-40+490*sin(a);eye[1]=-490*cos(a);eye[2]=590;
        target[0]=-40;target[1]=0;target[2]=70;
    } else {
        if(mode==2)p=1-p;
        for(k=0;k<3;k++){target[k]=entry_camera[k+3];eye[k]=entry_camera[k]+(target[k]-entry_camera[k])*p*.84;}
    }
    for(k=0;k<3;k++)f[k]=target[k]-eye[k];
    norm=sqrt(f[0]*f[0]+f[1]*f[1]+f[2]*f[2]);for(k=0;k<3;k++)f[k]/=norm;
    norm=sqrt(f[0]*f[0]+f[1]*f[1]);r[0]=f[1]/norm;r[1]=-f[0]/norm;r[2]=0;
    d[0]=f[1]*r[2]-f[2]*r[1];d[1]=f[2]*r[0]-f[0]*r[2];d[2]=f[0]*r[1]-f[1]*r[0];
    for(i=0;i<64000;i++){depthbuffer[i]=0;visible_ids[i]=~0u;}
    for(vi=0;vi<vn;vi++) {
        double px[3],py[3],iz[3],area;int xmin,xmax,ymin,ymax,color;
        meshtri *m;
        i=selected?selected[vi]:vi;m=&mesh[i];
        if(mode==0 && m->group!=1 && m->group!=4)continue;
        if(mode!=0 && (m->group==1||m->group==4))continue;
        for(k=0;k<3;k++) {
            double vx=m->v[k*3]/8.0-eye[0]+(mode==0&&m->group==4?210*ease(t/3):0),vy=m->v[k*3+1]/8.0-eye[1],vz=m->v[k*3+2]/8.0-eye[2]+(mode==0&&m->group==4?split:0);
            double z=vx*f[0]+vy*f[1]+vz*f[2];if(z<8)break;
            iz[k]=1/z;px[k]=160+240*(vx*r[0]+vy*r[1]+vz*r[2])/z;py[k]=100+200*(vx*d[0]+vy*d[1]+vz*d[2])/z;
        }
        if(k!=3)continue;
        area=(px[1]-px[0])*(py[2]-py[0])-(py[1]-py[0])*(px[2]-px[0]);if(fabs(area)<.05)continue;
        xmin=(int)clamp(floor(fx_min(px[0],fx_min(px[1],px[2]))),0,319);xmax=(int)clamp(ceil(fx_max(px[0],fx_max(px[1],px[2]))),0,319);
        ymin=(int)clamp(floor(fx_min(py[0],fx_min(py[1],py[2]))),22,176);ymax=(int)clamp(ceil(fx_max(py[0],fx_max(py[1],py[2]))),22,176);
        if(m->group==2)color=28;else color=m->color;
        for(y=ymin;y<=ymax;y++)for(x=xmin;x<=xmax;x++) {
            double a=((px[1]-x-.5)*(py[2]-y-.5)-(py[1]-y-.5)*(px[2]-x-.5))/area;
            double b=((px[2]-x-.5)*(py[0]-y-.5)-(py[2]-y-.5)*(px[0]-x-.5))/area;
            double c=1-a-b,z;
            if(a<0||b<0||c<0)continue;z=a*iz[0]+b*iz[1]+c*iz[2];
            if(z>depthbuffer[y*320+x]){depthbuffer[y*320+x]=(float)z;visible_ids[y*320+x]=i;if(m->group==2) {
                double wx=(a*iz[0]*m->v[0]+b*iz[1]*m->v[3]+c*iz[2]*m->v[6])/(z*8);
                double wz=(a*iz[0]*m->v[2]+b*iz[1]*m->v[5]+c*iz[2]*m->v[8])/(z*8);
                int tx=(int)((wx+120)*640/240),ty=(int)((420-wz)*288/192);
                frame[y*320+x]=(tx>=0&&tx<640&&ty>=0&&ty<288&&boot_screen[ty*640+tx])?115:18;
            } else frame[y*320+x]=(unsigned char)color;}
        }
    }
    if(mode==0)centered(181,"U880 / RAM / DISPLAY CONTROLLER",171);
}
static void glenz(double t,double length) { source_mesh(t,length,0); }
static void hardware(double t,double length,int display) {
    int x,y,stage=(int)clamp(t/length*3,0,2),image=display?2:stage;
    double local=t/length*3-stage,zoom=1.1+ease(local)*.5;
    double cx=focus[image*2],cy=focus[image*2+1];
    for(y=25;y<147;y++)for(x=0;x<320;x++)
        frame[y*320+x]=(unsigned char)sample(image,cx+(x-160)*2/zoom,cy+(y-86)*2/zoom);
    for(x=0;x<4;x++) {
        int xx=30+x*85,active=display?x>=2:x<=stage;
        line(xx,157,xx+60,157,active?166:45);
        if(x<3){double phase=fmod(t*1.3,1);disk((int)(xx+60+phase*25),157,2,active?171:40);}
    }
    text(22,163,"KEY",152);text(107,163,"U880",152);text(192,163,"RAM",152);text(267,163,"CRT",152);
    if(display) {
        /* Illustrate character fetch -> glyph row -> raster, not an OS screen. */
        for(y=0;y<7;y++)for(x=0;x<5;x++) {
            int on=(y==0&&x>0&&x<4)||(y==3)||(x==0&&y>0)||(x==4&&y>0);
            if(on && y<1+(int)(local*7))disk(264+x*7,45+y*7,2,170);
        }
    }
    centered(181,display?(stage==0?"VIDEO RAM / CHARACTER FETCH":stage==1?"GLYPH ROW / PIXEL PATTERN":"RASTER SCAN / GREEN PHOSPHOR"):
        (stage==0?"KEYSTROKE / U880 READS INPUT":stage==1?"INSTRUCTIONS / MAIN MEMORY":"CHARACTER / DISPLAY MEMORY"),171);
}
static void techno(double t,double length) { hardware(t,length,0); }
static void plasma(double t,double length) { hardware(t,length,1); }

static void terrain(double t,double length,int mountain) {
    int x,z,top[320],y;double travel=t*24;
    for(x=0;x<320;x++)top[x]=177;
    for(z=10;z<300;z+=2)for(x=0;x<320;x+=2) {
        double u=320+(x-160)*z/80.0,v=fmod(travel+z*2,399);
        unsigned h=sample(0,u,v);int sy=(int)(85+(60-h*.45)*100/z);
        if(mountain)sy=(int)(100+(40-22*sin(u*.025)-h*.25)*100/z);
        sy=(int)clamp(sy,26,177);
        for(y=sy;y<top[x];y++){pixel(x,y,15+h*3/4);pixel(x+1,y,15+h*3/4);}if(sy<top[x])top[x]=sy;
    }
    if(mountain)text((int)(320-t*38),65,"ROBOTRON 1715M / CIRCUIT HORIZON",166);
    centered(181,mountain?"ROBOTRON / CIRCUIT HORIZON":"PCB LANDSCAPE / ARTISTIC HEIGHT FIELD",170);
}
static void mirror(double t,double length) {
    int x,y;double cx=160+35*sin(t*.4),cy=100;
    for(y=27;y<176;y++)for(x=0;x<320;x++) {
        double dx=(x-cx)/70,dy=(y-cy)/67,r=dx*dx+dy*dy*1.44;
        if(r<1) { double z=sqrt(1-r);frame[y*320+x]=(unsigned char)sample(0,320+dx*z*280+40*sin(t*.3),200+dy*z*180); }
        else if(y>157)pixel(x,y,15+(int)(10*(1+sin(x*.08+y*.3+t))));
    }
    text((int)(320-t*36),35,"ROBOTRON / SECOND REALITY",166);
    centered(181,"REFLECTION / COMPONENT LANDSCAPE",171);
}
static void jelly(double t,double length) {
    unsigned i;double amp=25*(1-ease((t-length*.35)/(length*.5)));
    for(i=0;i<point_count;i++)pixel(points[i*2],(int)(points[i*2+1]+amp*sin(points[i*2]*.045-t*3)),160+i%20);
    centered(181,"ROBOTRON 1715M",170);
}
static void screen_transition(double t,double length,int reverse) {
    source_mesh(t,length,reverse?2:1);
    centered(181,reverse?"FROM PIXELS TO THE MACHINE":"INTO THE DISPLAY CONTROLLER",170);
}
static void render(unsigned scene,double t,double length) {
    int y;unsigned pi;scene_gain=1;
    for(pi=1;pi<128;pi++) {
        double red=.28,green=.47,blue=.37;
        if(scene==1){red=.39;green=.44;blue=.49;}
        if(scene==4){red=.48;green=.38;blue=.22;}
        if(scene==5){red=.16;green=.49;blue=.26;}
        palette[pi*3]=(unsigned char)(pi*red);palette[pi*3+1]=(unsigned char)(pi*green);palette[pi*3+2]=(unsigned char)(pi*blue);
    }memset(frame,0,sizeof(frame));
    switch(scene) {
    case 0:identity(t,length);break;case 1:lens(t,length);break;case 2:tunnel(t,length);break;
    case 3:glenz(t,length);break;case 4:techno(t,length);break;case 5:plasma(t,length);break;
    case 6:terrain(t,length,0);break;case 7:mirror(t,length);break;case 8:terrain(t,length,1);break;case 9:jelly(t,length);break;
    case 10:screen_transition(t,length,0);break;case 11:screen_transition(t,length,1);break;
    }
    for(y=0;y<20;y++)memset(frame+y*320,0,320);
    text(10,5,"ROBOTRON 1715M",165);
    text(224,5,scene==0?"AWAKEN":scene==1?"INSPECT":scene==2?"DATA FLOW":scene==3?"INSIDE":scene==4?"KEY TO RAM":scene==5?"RAM TO CRT":scene>=10?"DISPLAY":names[scene],125);
    line(10,20,309,20,35);line(10,177,309,177,35);
}
static void assets(void) {
    FILE *f;unsigned i;int x,y;
    #ifdef FX_HOST
    bake_visibility=getenv("FX_VIS_BAKE")!=0;
    f=fopen(bake_visibility?"FX.MSH":"FX.DRW","rb");if(!f)f=fopen("FX.MSH","rb");
#else
    f=fopen("FX.DRW","rb");
#endif
    if(!f)fail("FX.MSH");mesh_count=read32(f);
    if(mesh_count<1||mesh_count>250000)fail("mesh count");
    if(fread(entry_camera,4,6,f)!=6)fail("mesh camera");
    mesh=malloc(mesh_count*sizeof(meshtri));if(!mesh)fail("mesh memory");
    if(fread(mesh,sizeof(meshtri),mesh_count,f)!=mesh_count||fread(boot_screen,1,sizeof(boot_screen),f)!=sizeof(boot_screen)||fgetc(f)!=EOF)fail("mesh data");fclose(f);
    visible_flags=calloc(mesh_count,1);if(!visible_flags)fail("visibility flags");
#ifdef FX_HOST
    bake_visibility=getenv("FX_VIS_BAKE")!=0;
#endif
    if(!bake_visibility) {
        unsigned n,j,k,scene,count;char magic[4];
        f=fopen("FX.VIS","rb");
        if(f) {
            if(fread(magic,1,4,f)!=4||memcmp(magic,"FV02",4))fail("visibility header");
            n=read32(f);if(n>12)fail("visibility scenes");
            for(j=0;j<n;j++){scene=read32(f);count=read32(f);if(scene>11||count<2||count>512)fail("visibility poses");vis_frames[scene]=count;
                for(k=0;k<count;k++){unsigned q,c=read32(f);if(c>mesh_count)fail("visibility count");vis_count[scene][k]=c;visibility[scene][k]=malloc(c*4+1);
                    if(!visibility[scene][k])fail("visibility memory");for(q=0;q<c;q++){unsigned char b[2];unsigned id;if(fread(b,1,2,f)!=2)fail("visibility truncated");id=b[0]+256u*b[1];if(id>=mesh_count)fail("visibility id");visibility[scene][k][q]=id;}}
            }
            if(fgetc(f)!=EOF)fail("visibility tail");fclose(f);
        }
#ifndef FX_HOST
        else fail("FX.VIS");
#endif
    }
    pictures=malloc(1536000);if(!pictures)fail("picture memory");load_bytes("FX.IMG",pictures,1536000);load_bytes("FX.LOC",focus,sizeof(focus));
    load_bytes("FX.FNT",font,sizeof(font));f=fopen("FX.PTS","rb");if(!f)fail("FX.PTS");point_count=read32(f);
    if(point_count>20000)fail("point count");points=malloc(point_count*4);if(!points||fread(points,4,point_count,f)!=point_count)fail("points");fclose(f);
    for(i=0;i<1024;i++)sine[i]=(int)(32*sin(i*PI/512));
    for(i=0;i<3;i++) {
        memset(frame,0,sizeof(frame));picture(i,0,24,320,151);memcpy(backdrop[i],frame,64000);
        for(y=0;y<62;y++)for(x=0;x<90;x++)detailpic[i][y*90+x]=(unsigned char)sample(i+3,x*639.0/90,y*399.0/62);
    }
    memset(palette,0,sizeof(palette));
    for(i=192;i<256;i++){int k;for(k=0;k<3;k++)palette[i*3+k]=(unsigned char)(material_rgb[(i-192)/8][k]*(.25+.75*((i-192)%8)/7)*63/255);}
    for(i=1;i<128;i++){palette[i*3]=(unsigned char)(i*.28);palette[i*3+1]=(unsigned char)(i*.47);palette[i*3+2]=(unsigned char)(i*.37);}
    for(i=128;i<192;i++){palette[i*3]=35+(i-128)*28/63;palette[i*3+1]=26+(i-128)*31/63;palette[i*3+2]=12+(i-128)*30/63;}
}
#ifdef FX_HOST
int main(int argc,char **argv) {
    FILE *f;unsigned i;double t,length;unsigned scene;
    if(argc!=5)return 2;scene=atoi(argv[1]);t=atof(argv[2]);length=atof(argv[3]);if(scene>11||length<=0)return 2;
    assets();render(scene,t,length);
    if(getenv("FX_VIS_WRITE")) {
        unsigned n=0;FILE *v=fopen(getenv("FX_VIS_WRITE"),"wb");if(!v)return 3;
        for(i=0;i<64000;i++)if(visible_ids[i]<mesh_count)visible_flags[visible_ids[i]]=1;
        for(i=0;i<mesh_count;i++)n+=visible_flags[i]!=0;fwrite(&n,4,1,v);
        for(i=0;i<mesh_count;i++)if(visible_flags[i])fwrite(&i,4,1,v);fclose(v);
    }
    f=!strcmp(argv[4],"-")?stdout:fopen(argv[4],"wb");if(!f)return 3;fprintf(f,"P6\n320 200\n255\n");
    for(i=0;i<64000;i++){unsigned c=frame[i];fputc(palette[c*3]*255/63,f);fputc(palette[c*3+1]*255/63,f);fputc(palette[c*3+2]*255/63,f);}fclose(f);return 0;
}
#else
#pragma pack(push,1)
typedef struct { unsigned edi,esi,ebp,reserved,ebx,edx,ecx,eax;unsigned short flags,es,ds,fs,gs,ip,cs,sp,ss; } rm_regs;
#pragma pack(pop)
static void real_interrupt(unsigned n,rm_regs *r) {
    union REGS in,out;struct SREGS seg;memset(&in,0,sizeof(in));segread(&seg);in.w.ax=0x300;in.h.bl=n;in.x.edi=(unsigned)r;seg.es=seg.ds;r->flags=0x200;
    int386x(0x31,&in,&out,&seg);if(out.x.cflag)fail("DPMI interrupt");
}
static unsigned dis(unsigned service) { rm_regs r;memset(&r,0,sizeof(r));r.ebx=service;real_interrupt(0xfc,&r);return r.eax&65535; }
static unsigned snapshot(unsigned *tick) { rm_regs r;memset(&r,0,sizeof(r));r.ebx=11;real_interrupt(0xfc,&r);if((r.ecx&65535)!=0x1715)fail("launcher bridge");*tick=r.edx&65535;return r.eax&65535; }
static void set_palette(double scale) { unsigned i;outp(0x3c8,0);for(i=0;i<768;i++)outp(0x3c9,(unsigned)(palette[i]*scale)); }
int main(void) {
    FILE *f;char magic[4];unsigned first,last,count,nclock,*clock,i,j,tick,oldtick=0,oldpos=65535,pos,ms,frames=0;
    unsigned entries[16][5];rm_regs r;int active=-1;double t,length,fade;
    const unsigned short *vector=(unsigned short *)(0xfc*4);const unsigned short *sig=(unsigned short *)((unsigned)vector[1]*16+vector[0]-4);
    if(vector[0]<4||sig[0]!=0x0fc0||sig[1]!=0x0fc0){puts("Run RT1715.EXE");return 3;}
    trace=fopen(FX_POST?"POST.LOG":"FX.LOG","wt");if(!trace)return 3;
    f=fopen(FX_POST?"POST.TIM":"FX.TIM","rb");if(!f)fail("schedule");
    if(fread(magic,1,4,f)!=4||memcmp(magic,"FX01",4))fail("schedule header");first=read32(f);last=read32(f);count=read32(f);nclock=read32(f);
    if(last<first||last>255||count<1||count>16||nclock!=(last-first+1)*64)fail("schedule bounds");
    clock=malloc(nclock*4);if(!clock)fail("clock memory");for(i=0;i<nclock;i++)clock[i]=read32(f);
    for(i=0;i<count;i++)for(j=0;j<5;j++)entries[i][j]=read32(f);if(fgetc(f)!=EOF)fail("schedule tail");fclose(f);
    for(i=0;i<count;i++)if(entries[i][0]>11||entries[i][1]>=entries[i][2]||entries[i][3]>=entries[i][4])fail("schedule entry");
    fprintf(trace,"SCHEDULE\n");fflush(trace);assets();fprintf(trace,"ASSETS\n");fflush(trace);dis(0);fprintf(trace,"DIS\n");fflush(trace);memset(&r,0,sizeof(r));r.eax=0x13;real_interrupt(0x10,&r);fprintf(trace,"VIDEO\n");fflush(trace);set_palette(0);fprintf(trace,"PALETTE\n");fflush(trace);
    for(;;) {
        pos=snapshot(&tick);if(oldpos==65535){fprintf(trace,"INITIAL order=%u row=%u tick=%u\n",pos>>6,pos&63,tick);fclose(trace);trace=fopen(FX_POST?"POST.LOG":"FX.LOG","at");}
        if(pos!=oldpos){oldpos=pos;oldtick=tick;}
        if(dis(2)){fprintf(trace,"CANCELLED\n");fclose(trace);return 1;}
        if(pos>=entries[count-1][2])break;
        if(pos<first*64){dis(1);continue;}if(pos>last*64+63)fail("clock position");
        ms=clock[pos-first*64]+((tick-oldtick)&65535)*1000/70;
        i=0;while(i+1<count&&pos>=entries[i][2])i++;
        if(active!=(int)i){active=i;fprintf(trace,"ENTRY scene=%s order=%u row=%u frames=%u\n",names[entries[i][0]],pos>>6,pos&63,frames);fflush(trace);}
        t=(double)((int)ms-(int)entries[i][3])/1000;length=(entries[i][4]-entries[i][3])/1000.0;
        render(entries[i][0],t,length);fade=fx_min(ease(t/.35),ease((length-t)/.35));
        dis(1);memcpy((void *)0xa0000,frame,64000);set_palette(fade*scene_gain);frames++;
    }
    set_palette(0);memset((void *)0xa0000,0,64000);
    fprintf(trace,"END order=%u row=%u frames=%u\nCOMPLETE\n",pos>>6,pos&63,frames);fclose(trace);
    free(clock);free(pictures);free(points);free(mesh);return 0;
}
#endif
