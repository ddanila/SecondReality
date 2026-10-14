/* Protected-mode VISU player. Assets and tracker remain the original formats. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <conio.h>
#include <time.h>
#include "pm.h"
#include "MUSIC.H"
#define MAXOBJ 256
static struct { object *o;long dist;int index,on; } scene[MAXOBJ];
static rmatrix camera;
static object camera_object;
static int object_count,order[MAXOBJ],currframe,finished;
static unsigned char *animation,*cursor,*animation_end;
static unsigned fov;
static FILE *trace;
static unsigned last_position=65535,last_tick;
static void fail(const char *s) { if(trace) { fprintf(trace,"ERROR %s\n",s);fclose(trace); } puts(s);exit(3); }
static void *allocate(size_t n) { void *p=calloc(1,n);if(!p) fail("Out of protected-mode memory");return p; }
static unsigned char *readfile(const char *name,size_t *size) {
    FILE *f=fopen(name,"rb");unsigned char *p;long n;
    if(!f) fail(name);fseek(f,0,SEEK_END);n=ftell(f);rewind(f);
    if(n<0) fail("Invalid asset size");p=allocate(n+1);
    if(fread(p,1,n,f)!=(size_t)n) fail("Short asset read");fclose(f);*size=n;return p;
}
static unsigned word(const unsigned char *p) { return p[0]|((unsigned)p[1]<<8); }
static unsigned long dword(const unsigned char *p) { return word(p)|((unsigned long)word(p+2)<<16); }
static object *load_object(const char *name) {
    size_t size;unsigned char *data=readfile(name,&size),*p=data,*end=data+size,*d;
    unsigned long length;object *o=allocate(sizeof(*o));int i,j,n;unsigned offset;
    o->flags=0xf001;o->r=allocate(sizeof(rmatrix));o->r0=allocate(sizeof(rmatrix));
    while(p+8<=end) {
        length=dword(p+4);d=p+8;if(length>(unsigned long)(end-d)) fail("Invalid object chunk");
        if(!memcmp(p,"END ",4)) break;
        if(!memcmp(p,"NAME",4)) { if(!memchr(d,0,length)) fail("Invalid object name");o->name=(char *)d; }
        else if(!memcmp(p,"VERT",4)) {
            if(length<4) fail("Invalid vertices");o->vnum=word(d);
            if(o->vnum>500 || length<4+o->vnum*sizeof(vlist)) fail("Invalid vertex count");
            o->v0=(vlist *)(d+4);
        } else if(!memcmp(p,"NORM",4)) {
            if(length<4) fail("Invalid normals");o->nnum=word(d);o->nnum1=word(d+2);
            if(o->nnum>500 || length<4+o->nnum*sizeof(nlist)) fail("Invalid normal count");
            o->n0=(nlist *)(d+4);
        } else if(!memcmp(p,"POLY",4)) { o->pd=d; }
        else if(!memcmp(p,"ORD0",4)) { o->pl[0]=(unsigned short *)d; }
        p=d+length;
    }
    if(!o->name || !o->v0 || !o->n0 || !o->pd || !o->pl[0]) fail("Incomplete object");
    n=o->pl[0][0]-3;
    if(n<0 || (unsigned char *)(o->pl[0]+n+3)>end) fail("Invalid face list");
    for(i=0;i<n;i++) {
        unsigned short *face;
        offset=o->pl[0][i+2];if(o->pd+offset+6>end) fail("Invalid polygon offset");
        face=(unsigned short *)(o->pd+offset);j=face[0]&255;
        if(j<3 || j>8 || (unsigned char *)(face+j+3)>end || face[2]>=o->nnum) fail("Invalid polygon");
        while(j--) {
            unsigned vertex=face[j+3];
            if(vertex>=o->vnum) fail("Invalid polygon vertex");
            if((face[0]&F_GOURAUD) && (unsigned short)o->v0[vertex].normal>=o->nnum)
                fail("Invalid Gouraud normal");
        }
    }
    rt_bounds_init(o);return o;
}
static unsigned byte(void) { if(cursor>=animation_end) fail("Truncated animation");return *cursor++; }
static long delta(unsigned flags) {
    unsigned long value;unsigned kind=flags&3;
    if(!kind) return 0;
    value=byte();if(kind==1) return (signed char)value;
    value|=(unsigned long)byte()<<8;if(kind==2) return (short)value;
    value|=(unsigned long)byte()<<16;value|=(unsigned long)byte()<<24;return (long)value;
}
static void next_frame(void) {
    unsigned a,b,onum=0;unsigned long flags;rmatrix *r;
    while(!finished) {
        a=byte();
        if(a==255) { a=byte();if(a<=127) { fov=a<<8;return; } if(a==255) { finished=1;return; } }
        if((a&0xc0)==0xc0) { onum=(a&63)<<4;a=byte(); }
        onum=(onum&0xff0)|(a&15);if(onum>=(unsigned)object_count) fail("Invalid animation object");
        if((a&0xc0)==0x80) scene[onum].on=1;
        if((a&0xc0)==0x40) scene[onum].on=0;
        r=scene[onum].o->r0;flags=0;
        for(b=0;b<((a>>4)&3);b++) flags|=(unsigned long)byte()<<(b*8);
        r->x+=delta(flags);r->y+=delta(flags>>2);r->z+=delta(flags>>4);
        for(b=0;b<9;b++) if(flags&(0x80UL<<b)) r->m[b]+=delta((flags&64)?2:1);
    }
}
static int music_frame(unsigned *position) {
    unsigned tick,pos=rt_snapshot(&tick),ord=pos>>6,row=pos&63;long frame;
    *position=pos;
    if(pos!=last_position) { last_position=pos;last_tick=tick; }
    if(ord<19) return 0;if(ord>26) return 4200;
    frame=(long)rt_row_cs[ord-19][row]*70/100;
    frame+=(unsigned short)(tick-last_tick);return frame;
}
static void fadeset(unsigned char *vram) {
    int y;
    outpw(0x3c4,0x0f02);
    for(y=0;y<200;y++) {
        int mid=y>=25 && y<175;
        memset(vram+y*80,mid?254:0,17);memset(vram+y*80+17,mid?253:252,47);
        outpw(0x3c4,0x0e02);vram[y*80+63]=mid?254:0;outpw(0x3c4,0x0f02);
        memset(vram+y*80+64,mid?254:0,16);
    }
}
static void intro(unsigned char *palette) {
    unsigned char p[768];int a,b;
    rt_video_init();memset(p,0,sizeof(p));for(a=3;a<192;a++) p[a]=63;
    for(b=0;b<33;b++) {
        for(a=3;a<762;a++) p[a]=p[a]+2>63?63:p[a]+2;
        rt_wait();rt_palette(p);
    }
    for(b=0;b<16;b++) rt_wait();
    fadeset((unsigned char *)0xa0000);rt_wait();
    outp(0x3d4,9);outp(0x3d5,(inp(0x3d5)&0xf0)|0x80);rt_wait();
    for(b=1;b<4;b++) fadeset((unsigned char *)(0xa0000+b*16384));
    for(b=0;b<16;b++) rt_wait();
    for(b=0;b<33;b++) {
        for(a=3;a<759;a++) p[a]=p[a]<2?0:p[a]-2;
        for(a=759;a<765;a++) p[a]=p[a]+2>63?63:p[a]+2;
        rt_wait();rt_palette(p);
    }
    memset(palette+252*3,0,12);memset(palette+253*3,63,6);rt_palette(palette);
}
static void render(unsigned page) {
    int i,j,n=0,index;long distance;object *o;
    rt_draw_page(page);rt_color_begin();rt_camera(fov);rt_begin();
    for(i=1;i<object_count;i++) if(scene[i].on) {
        o=scene[i].o;*o->r=*o->r0;calc_applyrmatrix(o->r,&camera);
        if(rt_bounds_culling && rt_bounds_outside(o)) continue;
        distance=o->name[1]=='_'?1000000000L:calc_singlez(o->pl[0][1],o->v0,o->r);
        scene[i].dist=distance;order[n++]=i;
    }
    for(i=0;i<n;i++) {
        index=order[i];distance=scene[index].dist;
        for(j=i-1;j>=0 && distance<scene[order[j]].dist;j--) order[j+1]=order[j];
        order[j+1]=index;
    }
    for(i=0;i<n;i++) rt_queue(scene[order[i]].o);
    rt_color_flush();rt_frames++;
}
/* No music/retrace waits here: identical decoded poses, timed render work only.
 * Uploads remain inside render(); hashing is outside the timed interval. */
static int benchmark(void) {
    static const int poses[]={420,980,1840,2660,3200,3750};
    unsigned i,j;clock_t start,elapsed;unsigned long hash;FILE *f;
    extern unsigned char rt_color[64000];
    f=fopen("BENCH.LOG","wt");if(!f) fail("Cannot create benchmark log");
    rt_video_init();rt_ram_color=1;
    for(i=0;i<sizeof(poses)/sizeof(poses[0]);i++) {
        while(currframe<poses[i] && !finished) { next_frame();currframe+=2; }
        if(finished) fail("Benchmark pose beyond animation");
        render(0); /* warm-up outside measurement */
        start=clock();
        for(j=0;j<120;j++) render(0);
        elapsed=clock()-start;hash=2166136261UL;
        for(j=0;j<64000;j++) hash=(hash^rt_color[j])*16777619UL;
        fprintf(f,"POSE %d iterations=120 ticks=%lu hz=%lu color=%08lx vertices=%lu triangles=%lu spans=%lu\n",
                poses[i],(unsigned long)elapsed,(unsigned long)CLOCKS_PER_SEC,hash,
                rt_vertices,rt_triangles,rt_spans);fflush(f);
        rt_vertices=rt_triangles=rt_spans=0;
    }
    fprintf(f,"PASS\n");fclose(f);return 0;
}

int main(int argc,char **argv) {
    size_t size;unsigned char *materials;unsigned offset,pos,tick,page=0;
    int bench=argc>1 && !strcmp(argv[1],"/bench");
    int i,j,index,target,cue=0;char name[32];FILE *config;
    typedef char check_vertex_size[sizeof(vlist)==16?1:-1];
    typedef char check_normal_size[sizeof(nlist)==8?1:-1];
    if(argc>1 && !strcmp(argv[1],"/direct")) rt_ram_color=0;
    config=fopen("PM.CFG","rt");
    if(config) {
        if(fscanf(config,"%31s",name)==1) {
            if(!strcmp(name,"direct")) rt_ram_color=0;
            else if(strcmp(name,"ram")) fail("Invalid PM.CFG color backend");
        }
        fclose(config);
    }
    if(!bench) { rt_dis(0);rt_snapshot(&tick); }
    trace=fopen("FLIGHT.LOG","wt");if(!trace) fail("Cannot create FLIGHT.LOG");
    fprintf(trace,"PROTECTED DOS32A flat-memory color=%s data=%p\n",rt_ram_color?"RAM":"VGA",(void *)scene);fflush(trace);
    materials=readfile("U2E.00M",&size);
    if(size<784) fail("Invalid materials");offset=dword(materials+4);
    if(offset+2>size) fail("Invalid scene index");object_count=word(materials+offset);
    if(object_count<2 || object_count>MAXOBJ || offset+object_count*2>size) fail("Invalid scene count");
    camera_object.r=camera_object.r0=&camera;scene[0].o=&camera_object;
    for(i=1;i<object_count;i++) {
        index=word(materials+offset+i*2);scene[i].index=index;
        for(j=1;j<i && scene[j].index!=index;j++);
        if(j<i) {
            scene[i].o=allocate(sizeof(object));*scene[i].o=*scene[j].o;
            scene[i].o->r=allocate(sizeof(rmatrix));scene[i].o->r0=allocate(sizeof(rmatrix));
        } else { sprintf(name,"U2E.%03d",index);scene[i].o=load_object(name); }
    }
    animation=readfile("U2E.0AB",&size);cursor=animation;animation_end=animation+size;
    if(bench) return benchmark();
    intro(materials+16);rt_dis(0);
    do { pos=rt_snapshot(&tick);if((pos>>6)<19) rt_wait(); } while((pos>>6)<19 && !rt_dis(2));
    next_frame();currframe=2;
    while(!finished && !rt_dis(2)) {
        render(page);rt_wait();rt_show_page(page);page=(page+1)&3;
        target=music_frame(&pos);
        while(cue<2 && currframe>=(cue?3344:3186)) {
            fprintf(trace,"%s frame=%d order=%u row=%u\n",cue?"SWOOSH":"OVERVIEW",currframe,pos>>6,pos&63);
            fflush(trace);cue++;
        }
        /* A faster renderer must hold, rather than advance the timeline.
         * At most one animation step per two 70 Hz ticks (original 35 Hz data).
         * Slow frames still catch up by decoding skipped poses. */
        while(target<currframe+2 && !rt_dis(2)) { rt_wait();target=music_frame(&pos); }
        target=(target/2)*2;
        while(currframe<target && !finished) { next_frame();currframe+=2; }
    }
    pos=rt_snapshot(&tick);
    fprintf(trace,"END order=%u row=%u frame=%d\n",pos>>6,pos&63,currframe);
    fprintf(trace,"COUNTERS frames=%lu vertices=%lu triangles=%lu spans=%lu clipped=%lu ems_maps=0\n",
            rt_frames,rt_vertices,rt_triangles,rt_spans,rt_clipped);
    fclose(trace);rt_depth_end();return 0;
}
