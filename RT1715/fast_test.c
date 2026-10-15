/* Runs the actual real-mode kernels against portable reference operations. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stddef.h>
#include <dos.h>
#include <time.h>
#include "fast.h"
#include "vectors.h"
typedef struct { int x,y,z,reserved; } nlist;
#include "lighting.h"
static nlist light_normals[500];
static unsigned short __far actual_depth[8192],expected_depth[8192];
static unsigned char __far actual_video[1024],expected_video[1024];
static unsigned char __far source[16384],copied[16384];
static long __far points[3][4],actual_left[200],actual_right[200],expected_left[200],expected_right[200];
static rt_span_args args;
static int top,bottom;
static void reference_edges(void) {
    int i,j,y;
    long vx,vy,wx,wy,t,dx,x;
    for(y=top;y<bottom;y++) { expected_left[y]=0x7fffffffL;expected_right[y]=-0x7fffffffL; }
    for(i=0;i<3;i++) {
        j=(i+1)%3;vx=points[i][0];vy=points[i][1];wx=points[j][0];wy=points[j][1];
        if(vy>wy) { t=vx;vx=wx;wx=t;t=vy;vy=wy;wy=t; }
        if(vy==wy) continue;
        dx=((wx-vx)*65536L)/(wy-vy);x=vx*65536L+dx/2;
        for(y=(int)vy;y<(int)wy;y++,x+=dx) {
            if(x<expected_left[y]) expected_left[y]=x;
            if(x>expected_right[y]) expected_right[y]=x;
        }
    }
}
static void reference(void) {
    unsigned i,offset=args.depth_off/2,video=args.video_off,depth;
    long q=args.z,c=args.color;
    for(i=0;i<args.count;i++,offset+=4,video++,q+=args.dz,c+=args.dcolor) {
        depth=(unsigned)(q>>6);
        if(args.decal && depth<65535) depth++;
        if(depth>=expected_depth[offset]) {
            expected_depth[offset]=depth;expected_video[video]=(unsigned char)(c>>6);
        }
    }
}
static int fail(const char *what,unsigned i) {
    printf("FAIL %s %u\n",what,i);return 1;
}
int main(void) {
    unsigned i,j,k,n,start;
    unsigned long uncached_total=0,cached_total=0;
    clock_t begin,c_ticks,asm_ticks;
    if(sizeof(rt_span_args)!=28 || offsetof(rt_span_args,z)!=12)
        return fail("ABI layout",sizeof(rt_span_args));
    for(i=0;i<sizeof(vectors)/sizeof(vectors[0]);i++)
        if(rt_muldiv(vectors[i][0],vectors[i][1],vectors[i][2])!=vectors[i][3])
            return fail("muldiv",i);
    printf("PASS arithmetic %u cases\n",i);
    for(i=0;i<16384;i++) source[i]=(unsigned char)(i*37+11);
    for(i=0;i<80;i++) {
        n=i<16?i:16300+i;start=i%7;
        memset(copied,0xa5,sizeof(copied));
        rt_copy386(copied+start,source+3,n);
        for(j=0;j<16384;j++)
            if(copied[j]!=(j>=start && j<start+n?source[j-start+3]:0xa5)) return fail("copy",i);
        rt_clear386(copied+start,n);
        for(j=0;j<16384;j++)
            if(copied[j]!=(j>=start && j<start+n?0:0xa5)) return fail("clear",i);
    }
    for(i=1;i<=513;i*=3) {
        memcpy(copied,source,sizeof(source));memcpy(expected_depth,source,sizeof(source));
        memmove(expected_depth,(unsigned char __far *)expected_depth+i,12000);
        rt_copy386(copied,copied+i,12000);
        if(memcmp(copied,expected_depth,sizeof(copied))) return fail("forward overlap",i);
    }
    printf("PASS bulk operations, alignment, tails, guards and forward overlap\n");
    args.depth_seg=FP_SEG(actual_depth);args.video_seg=FP_SEG(actual_video);
    for(i=0;i<200;i++) {
        for(j=0;j<8192;j++) actual_depth[j]=expected_depth[j]=(j*113U+i*71U);
        memset(actual_video,0xa5,sizeof(actual_video));memset(expected_video,0xa5,sizeof(expected_video));
        start=i%4;n=i%5==0?0:1+i*17%500;
        /* Include spans ending at the final word of a 16K EMS page. */
        if(i%3==0 && n) start=8191-(n-1)*4;
        args.depth_off=FP_OFF(actual_depth)+start*2;
        args.video_off=FP_OFF(actual_video)+13;args.count=n;args.decal=i&1;
        args.z=i%7==0?65535L*64:2000000L+i*700;
        args.dz=i%7==0?0:(i&2?97:-97);
        args.color=100L*64;args.dcolor=(int)(i%3)-1;
        rt_span386(&args);
        /* The C oracle uses array-relative offsets. */
        args.depth_off=start*2;args.video_off=13;reference();
        if(memcmp(actual_depth,expected_depth,sizeof(actual_depth))) return fail("span depth",i);
        if(memcmp(actual_video,expected_video,sizeof(actual_video))) return fail("span color",i);
    }
    printf("PASS spans 200 cases, both shade slopes, decals and page edges\n");
    for(i=0;i<500;i++) {
        light_normals[i].x=(int)(i*47%32768)-16384;
        light_normals[i].y=(int)(i*71%32768)-16384;
        light_normals[i].z=(int)(i*31%32768)-16384;
    }
    for(k=0;k<3;k++) {
        if(k==2) rt_light_epoch=(unsigned)-1;
        rt_light_begin();
        for(j=0;j<4;j++) for(i=0;i<500;i++) {
            if(rt_shade_cached(light_normals,i,j<<10)!=rt_shade(&light_normals[i],j<<10))
                return fail("cached lighting",i);
            if(rt_shade_cached(light_normals,i,j<<10)!=rt_shade(&light_normals[i],j<<10))
                return fail("lighting cache hit",i);
        }
        light_normals[0].x=-light_normals[0].x/2;
    }
    printf("PASS lighting 6000 cases plus cache hits, mode changes and generation wrap\n");
    for(i=0;i<500;i++) for(j=0;j<4;j++) {
        int value=rt_shade(&light_normals[i],j<<10);
        int bright=rt_readable_shade(value,&light_normals[i],j<<10,2);
        if(rt_readable_shade(value,&light_normals[i],j<<10,0)!=value)
            return fail("unmodified scene lighting",i);
        if(j && (bright<value || bright>((1<<(j+2))-1)))
            return fail("drone highlight escaped ramp",i);
        if(!j && bright!=value) return fail("unshaded drone material",i);
        value=rt_readable_shade(rt_shade(&light_normals[i],0x800),&light_normals[i],0x800,1);
        if(value<1 || value>6) return fail("charcoal key range",i);
    }
    printf("PASS local key/drone shading, ramp limits and unchanged scene materials\n");
    rt_light_begin();
    for(i=0;i<500;i++) {
        int value=rt_glass_shade_cached(light_normals,i);
        if(value<2 || value>13) return fail("guarded CRT reflection range",i);
        if(rt_glass_shade_cached(light_normals,i)!=value) return fail("CRT lighting cache",i);
    }
    for(i=0;i<500;i++) {
        int previous=0;
        for(j=0;j<=255;j+=17) {
            int value;rt_crt_brightness=j;rt_light_begin();
            value=rt_glass_shade_cached(light_normals,i);
            if(value<previous || value<2 || value>13 || (!j && value!=2))
                return fail("monotonic CRT warm-up",i);
            previous=value;
            value=rt_bezel_shade_cached(light_normals,i,0x800);
            if(value<2 || value>13)return fail("bezel ramp guard",i);
        }
    }
    rt_crt_brightness=255;rt_light_begin();
    printf("PASS soft CRT reflection, warm-up, bezel guards and cache\n");
    begin=clock();
    for(k=0;k<500;k++) for(j=0;j<6;j++) for(i=0;i<500;i++)
        uncached_total+=rt_shade(&light_normals[i],0xc00);
    c_ticks=clock()-begin;begin=clock();
    for(k=0;k<500;k++) {
        rt_light_begin();
        for(j=0;j<6;j++) for(i=0;i<500;i++) cached_total+=rt_shade_cached(light_normals,i,0xc00);
    }
    asm_ticks=clock()-begin;
    if(uncached_total!=cached_total) return fail("lighting checksum",0);
    printf("BENCH lighting direct=%lu cached=%lu ticks\n",(unsigned long)c_ticks,(unsigned long)asm_ticks);

    for(i=0;i<400;i++) {
        top=200;bottom=0;
        for(j=0;j<3;j++) {
            points[j][0]=(i*67+j*113)%321;points[j][1]=(i*41+j*79)%201;
            if(i%7==0) points[j][1]=100; /* Degenerate horizontal triangle. */
            if(points[j][1]<top) top=(int)points[j][1];
            if(points[j][1]>bottom) bottom=(int)points[j][1];
        }
        for(j=0;j<200;j++) actual_left[j]=actual_right[j]=expected_left[j]=expected_right[j]=0x41414141L;
        rt_edges386(points,actual_left,actual_right,top,bottom);reference_edges();
        if(memcmp(actual_left,expected_left,sizeof(actual_left)) ||
           memcmp(actual_right,expected_right,sizeof(actual_right))) return fail("edge walks",i);
    }
    printf("PASS edges 400 triangles, negative slopes, horizontal edges and guards\n");
    points[0][0]=0;points[0][1]=0;points[1][0]=320;points[1][1]=200;
    points[2][0]=20;points[2][1]=150;top=0;bottom=200;
    begin=clock();for(i=0;i<20000;i++) reference_edges();c_ticks=clock()-begin;
    begin=clock();for(i=0;i<20000;i++) rt_edges386(points,actual_left,actual_right,top,bottom);asm_ticks=clock()-begin;
    printf("BENCH edges C=%lu ASM=%lu ticks\n",(unsigned long)c_ticks,(unsigned long)asm_ticks);
    memset(actual_depth,0,sizeof(actual_depth));memset(expected_depth,0,sizeof(expected_depth));
    args.count=512;args.decal=0;args.z=2000000L;args.dz=-37;args.color=100L*64;args.dcolor=1;
    args.depth_off=0;args.video_off=0;
    begin=clock();for(i=0;i<20000;i++) reference();c_ticks=clock()-begin;
    args.depth_off=FP_OFF(actual_depth);args.video_off=FP_OFF(actual_video);
    begin=clock();for(i=0;i<20000;i++) rt_span386(&args);asm_ticks=clock()-begin;
    printf("BENCH span C=%lu ASM=%lu ticks_per_second=%lu\n",(unsigned long)c_ticks,(unsigned long)asm_ticks,(unsigned long)CLOCKS_PER_SEC);
    c_ticks=asm_ticks;args.dcolor=0;
    begin=clock();for(i=0;i<20000;i++) rt_span386(&args);asm_ticks=clock()-begin;
    printf("BENCH shading smooth=%lu flat=%lu ticks\n",(unsigned long)c_ticks,(unsigned long)asm_ticks);
    for(n=64;n<=16384;n*=16) {
        begin=clock();for(i=0;i<20000;i++) memcpy(copied,source,n);c_ticks=clock()-begin;
        begin=clock();for(i=0;i<20000;i++) rt_copy386(copied,source,n);asm_ticks=clock()-begin;
        printf("BENCH copy bytes=%u library=%lu ASM=%lu ticks\n",n,(unsigned long)c_ticks,(unsigned long)asm_ticks);
        if(n==16384) break;
    }
    begin=clock();for(i=0;i<20000;i++) _fmemset(copied,0,16384);c_ticks=clock()-begin;
    begin=clock();for(i=0;i<20000;i++) rt_clear386(copied,16384);asm_ticks=clock()-begin;
    printf("BENCH clear library=%lu ASM=%lu ticks\n",(unsigned long)c_ticks,(unsigned long)asm_ticks);
    printf("PASS native kernels\n");return 0;
}
