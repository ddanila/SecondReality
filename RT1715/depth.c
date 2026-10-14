/* 16-bit reciprocal depth in 128 KB of EMS, independent of VGA page flipping.
 * Convex polygons are clipped before fixed-point scan conversion. */
#include <stdlib.h>
#include <string.h>
#include "depth.h"
#ifdef RT_HOST_TEST
static unsigned short test_depth[64000];
static unsigned char test_color[64000];
unsigned rt_depth_at(int x,int y) { return test_depth[y*320+x]; }
unsigned rt_color_at(int x,int y) { return test_color[y*320+x]; }
#else
#include <dos.h>
#include <conio.h>
#include <stdio.h>
extern int far vramseg;
static unsigned frame_seg,handle;
static int active=0,mapped[4];
static void ems(unsigned ax,unsigned bx,unsigned dx) {
    union REGS r;
    r.x.ax=ax;r.x.bx=bx;r.x.dx=dx;int86(0x67,&r,&r);
    if(r.h.ah) { printf("Depth buffer EMS error %u\n",r.h.ah);exit(3); }
    if(ax==0x4100) frame_seg=r.x.bx;
    if(ax==0x4300) handle=r.x.dx;
}
static unsigned short far *page(unsigned logical) {
    unsigned physical=logical&3;
    if(mapped[physical]!=logical) {
        ems(0x4400|physical,logical,handle);mapped[physical]=logical;
    }
    return (unsigned short far *)MK_FP(frame_seg+physical*1024,0);
}
#endif
static long lx[200],rx[200],qstart[200],cstart[200];
static int clip_left=0,clip_right=320,clip_top=0,clip_bottom=200;
void rt_depth_window(int left,int right,int top,int bottom) {
    clip_left=left;clip_right=right;clip_top=top;clip_bottom=bottom;
}
void rt_depth_begin(void) {
#ifdef RT_HOST_TEST
    memset(test_depth,0,sizeof(test_depth));memset(test_color,255,sizeof(test_color));
#else
    unsigned i;
    if(!active) {
        ems(0x4100,0,0);ems(0x4300,8,0);
        for(i=0;i<4;i++) mapped[i]=-1;
        active=1;
    }
    for(i=0;i<8;i++) rt_clear386(page(i),16384);
#endif
}
void rt_depth_end(void) {
#ifndef RT_HOST_TEST
    if(active) { ems(0x4500,0,handle);active=0; }
#endif
}
static long coord(rt_vertex *v,int axis) { return axis ? v->y : v->x; }
static int clip(rt_vertex *in,rt_vertex *out,int n,int axis,long bound,int upper) {
    int i,m=0,inside,prev_inside;
    rt_vertex a,b,t,lo,hi;
    long av,bv,d,num;
    a=in[n-1];av=coord(&a,axis);prev_inside=upper ? av<=bound : av>=bound;
    for(i=0;i<n;i++) {
        b=in[i];bv=coord(&b,axis);inside=upper ? bv<=bound : bv>=bound;
        if(inside!=prev_inside) {
            /* Canonical edge direction gives adjacent faces identical rounded
             * intersections, even when they traverse the edge backwards. */
            lo=av<bv?a:b;hi=av<bv?b:a;
            d=coord(&hi,axis)-coord(&lo,axis);num=bound-coord(&lo,axis);
            t.x=lo.x+rt_muldiv(hi.x-lo.x,num,d);t.y=lo.y+rt_muldiv(hi.y-lo.y,num,d);
            t.z=lo.z+rt_muldiv(hi.z-lo.z,num,d);t.c=lo.c+rt_muldiv(hi.c-lo.c,num,d);
            if(axis) t.y=bound; else t.x=bound;
            out[m++]=t;
        }
        if(inside) out[m++]=b;
        a=b;av=bv;prev_inside=inside;
    }
    return m;
}
static void span(int y,int left,int right,long z,long dz,long c,long dc,int decal,int plane) {
    int x,end,first;
    unsigned long index;
    unsigned depth,offset,video_offset;
#ifndef RT_HOST_TEST
    unsigned short far *buffer;
    rt_span_args args;
#endif
    while(left<right) {
        index=(unsigned long)y*320+left;
        end=left+(int)(8192-(index&8191));if(end>right) end=right;
#ifndef RT_HOST_TEST
        buffer=page((unsigned)(index>>13));
#endif
        {
            long q,shade;
            first=left+((plane-left)&3);
            q=z+dz*(first-left);shade=c+dc*(first-left);
            offset=(unsigned)(((unsigned long)y*320+first)&8191);
            video_offset=y*80+(first>>2);
#ifndef RT_HOST_TEST
            if(first<end) {
                args.depth_seg=FP_SEG(buffer);args.depth_off=offset*2;
                args.video_seg=vramseg;args.video_off=video_offset;
                args.count=(end-first+3)/4;args.decal=decal;
                args.z=q;args.dz=(unsigned long)dz*4;
                args.color=shade;args.dcolor=(unsigned long)dc*4;
                rt_span386(&args);
            }
#else
            for(x=first;x<end;x+=4,q+=dz*4,shade+=dc*4,offset+=4,video_offset++) {
                depth=(unsigned)(q>>6);
                if(decal && depth<65535) depth++;
                index=(unsigned long)y*320+x;
                if(depth>=test_depth[index]) {
                    test_depth[index]=depth;test_color[index]=(unsigned char)(shade>>6);
                }
            }
#endif
        }
        z+=dz*(end-left);c+=dc*(end-left);left=end;
    }
}
static void triangle(rt_vertex *a,rt_vertex *b,rt_vertex *c,int decal) {
    rt_vertex vertices[3],v,w,t;
    int i,y,plane,miny=200,maxy=0,left,right;
    long area,qx,qy,cx=0,cy=0,x,dx,dy,z,shade;
    area=(b->x-a->x)*(c->y-a->y)-(c->x-a->x)*(b->y-a->y);
    if(!area) return;
    qx=rt_muldiv((b->z-a->z)*(c->y-a->y)-(c->z-a->z)*(b->y-a->y),64,area);
    qy=rt_muldiv((b->x-a->x)*(c->z-a->z)-(c->x-a->x)*(b->z-a->z),64,area);
    if(a->c!=b->c || a->c!=c->c) {
        cx=rt_muldiv((b->c-a->c)*(c->y-a->y)-(c->c-a->c)*(b->y-a->y),64,area);
        cy=rt_muldiv((b->x-a->x)*(c->c-a->c)-(c->x-a->x)*(b->c-a->c),64,area);
    }
    vertices[0]=*a;vertices[1]=*b;vertices[2]=*c;
    for(i=0;i<3;i++) { if(vertices[i].y<miny) miny=(int)vertices[i].y;if(vertices[i].y>maxy) maxy=(int)vertices[i].y; }
    if(miny>=maxy) return;
#ifndef RT_HOST_TEST
    rt_edges386(vertices,lx,rx,miny,maxy);
#else
    for(y=miny;y<maxy;y++) { lx[y]=0x7fffffffL;rx[y]=-0x7fffffffL; }
    for(i=0;i<3;i++) {
        v=vertices[i];w=vertices[(i+1)%3];if(v.y>w.y) { t=v;v=w;w=t; }
        dy=w.y-v.y;if(!dy) continue;
        dx=((w.x-v.x)*65536L)/dy;x=v.x*65536L+dx/2;
        for(y=(int)v.y;y<(int)w.y;y++,x+=dx) {
            if(x<lx[y]) lx[y]=x;
            if(x>rx[y]) rx[y]=x;
        }
    }
#endif
    for(y=miny;y<maxy;y++) {
        left=(int)((lx[y]+32767L)>>16);right=(int)((rx[y]+32767L)>>16);
        lx[y]=left;rx[y]=right;
        if(left>=right) continue;
        /* Unsigned intermediates make cancellation well-defined even for a
         * thin triangle whose extrapolated plane exceeds signed 32 bits. */
        z=(long)((unsigned long)a->z*64+(unsigned long)qx*(left-a->x)+
                 (unsigned long)qy*(y-a->y)+(qx+qy)/2);
        shade=(long)((unsigned long)a->c*64+(unsigned long)cx*(left-a->x)+
                     (unsigned long)cy*(y-a->y)+(cx+cy)/2);
        qstart[y]=z;cstart[y]=shade;
    }
    /* Select each VGA plane once per triangle, reusing scanline gradients. */
    for(plane=0;plane<4;plane++) {
#ifndef RT_HOST_TEST
        outpw(0x3c4,0x0002|(0x0100<<plane));
#endif
        for(y=miny;y<maxy;y++)
            if(lx[y]<rx[y]) span(y,(int)lx[y],(int)rx[y],qstart[y],qx,cstart[y],cx,decal,plane);
    }
}
void rt_raster(rt_vertex *vertices,int count,int decal) {
    rt_vertex a[16],b[16];
    int n=count,i,inside=1;
    if(n<3 || n>12) return;
    /* Most close-up faces are entirely in the viewport: avoid four clipping
     * passes and their vertex copies when no edge needs intersection. */
    for(i=0;i<n;i++)
        if(vertices[i].x<clip_left || vertices[i].x>clip_right ||
           vertices[i].y<clip_top || vertices[i].y>clip_bottom) { inside=0;break; }
    if(inside) {
        for(i=1;i<n-1;i++) triangle(&vertices[0],&vertices[i],&vertices[i+1],decal);
        return;
    }
    memcpy(a,vertices,n*sizeof(rt_vertex));
    n=clip(a,b,n,0,clip_left,0);if(n<3) return;
    n=clip(b,a,n,0,clip_right,1);if(n<3) return;
    n=clip(a,b,n,1,clip_top,0);if(n<3) return;
    n=clip(b,a,n,1,clip_bottom,1);if(n<3) return;
    for(i=1;i<n-1;i++) triangle(&a[0],&a[i],&a[i+1],decal);
}
