/* 16-bit reciprocal depth: flat protected-mode RAM or legacy EMS.
 * Convex polygons are clipped before fixed-point scan conversion. */
#include <stdlib.h>
#include <string.h>
#include "depth.h"
#ifdef RT_HOST_TEST
static unsigned short test_depth[64000];
static unsigned char test_color[64000];
unsigned rt_depth_at(int x,int y) { return test_depth[y*320+x]; }
unsigned rt_color_at(int x,int y) { return test_color[y*320+x]; }
#elif defined(RT_PM)
#include "pm.h"
#include <conio.h>
static unsigned short flat_depth[64000];
extern unsigned char rt_color[64000];
#ifdef RT_PM_VERIFY
unsigned rt_depth_at(int x,int y) { return flat_depth[y*320+x]; }
unsigned rt_color_at(int x,int y) { return rt_color[(x&3)*16000+y*80+(x>>2)]; }
#endif
#else
#include <dos.h>
#include <conio.h>
#include <stdio.h>
extern int far vramseg;
static unsigned frame_seg,handle;
static int active=0,mapped[4];
static rt_span_args direct_args;
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
#if defined(RT_HOST_TEST) || defined(RT_PM)
/* Optional experiments; the assembly scanline path remains the reference. */
int rt_occlusion=0,rt_tiles=0,rt_visible_spans=0;
unsigned long rt_occluded,rt_occlusion_queries;
static unsigned short coarse_depth[40*25];
static int band_top=0,band_bottom=200,flushing=0;
#define QUEUE_LIMIT 8192
typedef struct { rt_vertex v[3];int decal; } queued_triangle;
static queued_triangle *triangle_queue;
static unsigned queued;
static unsigned short *owners;
typedef struct { long x,y,origin; } surface_gradient;
static surface_gradient *surfaces;
static unsigned surface_count,current_surface;
static void flush_surfaces(void);
static unsigned short *depth_memory(void) {
#ifdef RT_HOST_TEST
    return test_depth;
#elif defined(RT_PM)
    return flat_depth;
#else
    return 0;
#endif
}
/* Cached minima may be old, but depth only increases within a frame. Refresh
 * a tile only when its old lower bound cannot prove complete occlusion. */
static int hidden_box(int left,int right,int top,int bottom,long maximum) {
    unsigned short *depth=depth_memory();int tx,ty,x,y;unsigned minimum,value;
    if(!depth || maximum<0 || maximum>=65535 || left>=right || top>=bottom) return 0;
    rt_occlusion_queries++;
    for(ty=top/8;ty<=(bottom-1)/8;ty++) for(tx=left/8;tx<=(right-1)/8;tx++) {
        minimum=coarse_depth[ty*40+tx];
        if(minimum<=maximum) {
            minimum=65535;
            for(y=ty*8;y<ty*8+8;y++) for(x=tx*8;x<tx*8+8;x++) {
                value=depth[y*320+x];if(value<minimum) minimum=value;
            }
            coarse_depth[ty*40+tx]=(unsigned short)minimum;
            if(minimum<=maximum) return 0;
        }
    }
    rt_occluded++;return 1;
}
static int hidden_triangle(const rt_vertex *a,const rt_vertex *b,const rt_vertex *c,long qx,long qy,int miny,int maxy,int decal) {
        long left=a->x,right=a->x;long long qlo,qhi,base;
        if(b->x<left) left=b->x;if(c->x<left) left=c->x;
        if(b->x>right) right=b->x;if(c->x>right) right=c->x;
        /* Bound the actual fixed-point depth plane over the entire box,
         * including half-pixel evaluation. Wrapped/extrapolated values are
         * deliberately not culled. Strict comparison preserves equal ties. */
        base=(long long)a->z*64-(long long)qx*a->x+(long long)qy*(miny-a->y)+(qx+qy)/2;
        qlo=base+(long long)qx*(qx<0?right:left)+(long long)qy*(qy<0?maxy-miny:0);
        qhi=base+(long long)qx*(qx<0?left:right)+(long long)qy*(qy<0?0:maxy-miny);
        if(qlo>=0 && qhi<4194240 && hidden_box((int)left,(int)right,miny,maxy,(long)(qhi>>6)+decal)) return 1;
    return 0;
}
#ifdef RT_PM
int __cdecl rt_triangle_hidden(const rt_triangle_args *args) {
    const rt_vertex *v=(const rt_vertex *)args->vertices;
    return hidden_triangle(v,v+1,v+2,args->qx,args->qy,args->top,args->bottom,args->decal);
}
#endif
#endif
static long lx[200],rx[200],qstart[200],cstart[200];
static int clip_left=0,clip_right=320,clip_top=0,clip_bottom=200;
void rt_depth_window(int left,int right,int top,int bottom) {
    clip_left=left;clip_right=right;clip_top=top;clip_bottom=bottom;
}
static void detail_begin(void);
static void detail_end(void);
static void detail_flush(void);
void rt_depth_begin(void) {
#ifdef RT_PM
    static int old_top=-1,old_bottom=-1;
#endif
#if defined(RT_HOST_TEST) || defined(RT_PM)
    if(rt_tiles && !triangle_queue) {
        triangle_queue=malloc(QUEUE_LIMIT*sizeof(*triangle_queue));if(!triangle_queue) exit(3);
    }
    if(rt_visible_spans && !owners) {
        owners=malloc(64000*sizeof(*owners));surfaces=malloc((QUEUE_LIMIT+1)*sizeof(*surfaces));
        if(!owners || !surfaces) exit(3);
    }
    detail_begin();
    queued=surface_count=0;band_top=0;band_bottom=200;
    if(rt_occlusion) memset(coarse_depth,0,sizeof(coarse_depth));
    if(rt_visible_spans) memset(owners,0,64000*sizeof(*owners));
#endif
#ifdef RT_HOST_TEST
    memset(test_depth,0,sizeof(test_depth));memset(test_color,255,sizeof(test_color));
#elif defined(RT_PM)
    if(old_top!=clip_top || old_bottom!=clip_bottom) {
        memset(flat_depth,0,sizeof(flat_depth));old_top=clip_top;old_bottom=clip_bottom;
    } else memset(flat_depth+clip_top*320,0,(clip_bottom-clip_top)*640);
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
#if defined(RT_HOST_TEST) || defined(RT_PM)
    detail_end();
    free(triangle_queue);free(owners);free(surfaces);
    triangle_queue=0;owners=0;surfaces=0;
#endif
#if !defined(RT_HOST_TEST) && !defined(RT_PM)
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
#ifdef RT_PM
    int first=left+((plane-left)&3);
    if(rt_profile || rt_visible_spans) {
        int x;unsigned value,index;long q=z+dz*(first-left),shade=c+dc*(first-left);
        for(x=first;x<right;x+=4,q=(long)((unsigned long)q+dz*4),shade=(long)((unsigned long)shade+dc*4)) {
            index=y*320+x;value=((unsigned long)q>>6)&65535;
            if(decal && value<65535) value++;
            if(rt_profile) rt_pixels++;
            if(value>=flat_depth[index]) {
                if(rt_profile) rt_pixels_passed++;
                flat_depth[index]=(unsigned short)value;
                if(rt_visible_spans) owners[index]=(unsigned short)current_surface;
                else if(rt_ram_color) rt_color[plane*16000+y*80+(x>>2)]=(unsigned char)(shade>>6);
                else rt_video[y*80+(x>>2)]=(unsigned char)(shade>>6);
            }
        }
        return;
    }
    if(first<right) {
        unsigned index=y*320+first,offset=y*80+(first>>2);
        unsigned char *dest=rt_ram_color?rt_color+plane*16000:rt_video;
        rt_span32(flat_depth+index,dest+offset,(right-first+3)/4,
                  z+dz*(first-left),dz*4,c+dc*(first-left),dc*4,decal);
        rt_spans++;
    }
#else
    int x,end,first;
    unsigned long index;
    unsigned depth,offset,video_offset;
#ifndef RT_HOST_TEST
    unsigned short far *buffer;
    unsigned logical;
#endif
    while(left<right) {
        index=(unsigned long)y*320+left;
        end=left+(int)(8192-(index&8191));if(end>right) end=right;
        {
            long q,shade;
            first=left+((plane-left)&3);
            q=z+dz*(first-left);shade=c+dc*(first-left);
            offset=(unsigned)(((unsigned long)y*320+first)&8191);
            video_offset=y*80+(first>>2);
#ifndef RT_HOST_TEST
            if(first<end) {
                logical=(unsigned)(index>>13);
                buffer=page(logical);
                direct_args.depth_seg=FP_SEG(buffer);direct_args.depth_off=offset*2;
                direct_args.video_off=video_offset;direct_args.count=(end-first+3)/4;
                direct_args.z=q;direct_args.color=shade;
                rt_span386(&direct_args);
            }
#else
            for(x=first;x<end;x+=4,q+=dz*4,shade+=dc*4,offset+=4,video_offset++) {
                depth=(unsigned)(q>>6);
                if(decal && depth<65535) depth++;
                index=(unsigned long)y*320+x;
                if(depth>=test_depth[index]) {
                    test_depth[index]=depth;
                    if(rt_visible_spans) owners[index]=(unsigned short)current_surface;
                    else test_color[index]=(unsigned char)(shade>>6);
                }
            }
#endif
        }
        z+=dz*(end-left);c+=dc*(end-left);left=end;
    }
#endif
}
static void triangle(rt_vertex *a,rt_vertex *b,rt_vertex *c,int decal) {
    rt_vertex vertices[3],v,w,t;
    int i,y,plane,miny=200,maxy=0,left,right;
    long area,qx,qy,cx=0,cy=0,x,dx,dy,z,shade;
#if defined(RT_HOST_TEST) || defined(RT_PM)
    if(rt_tiles && !flushing) {
        if(queued==QUEUE_LIMIT) rt_depth_flush();
        triangle_queue[queued].v[0]=*a;triangle_queue[queued].v[1]=*b;triangle_queue[queued].v[2]=*c;
        triangle_queue[queued++].decal=decal;return;
    }
#endif
    area=(b->x-a->x)*(c->y-a->y)-(c->x-a->x)*(b->y-a->y);
    if(!area) return;
#ifdef RT_PM
    rt_triangles++;
#endif
    vertices[0]=*a;vertices[1]=*b;vertices[2]=*c;
    for(i=0;i<3;i++) { if(vertices[i].y<miny) miny=(int)vertices[i].y;if(vertices[i].y>maxy) maxy=(int)vertices[i].y; }
#if defined(RT_HOST_TEST) || defined(RT_PM)
    if(miny<band_top) miny=band_top;if(maxy>band_bottom) maxy=band_bottom;
#endif
    if(miny>=maxy) return;
#ifdef RT_PM
    if(rt_triangle_kernel && !rt_profile && !rt_visible_spans) {
        rt_triangle_args args;
        args.vertices=vertices;args.depth=flat_depth;
        args.color=rt_ram_color?rt_color:rt_video;
        args.left=lx;args.right=rx;args.top=miny;args.bottom=maxy;
        args.area=area;
        args.decal=decal;args.ram=rt_ram_color;
        rt_spans+=rt_triangle32(&args);return;
    }
#endif
    qx=rt_muldiv((b->z-a->z)*(c->y-a->y)-(c->z-a->z)*(b->y-a->y),64,area);
    qy=rt_muldiv((b->x-a->x)*(c->z-a->z)-(c->x-a->x)*(b->z-a->z),64,area);
    if(a->c!=b->c || a->c!=c->c) {
        cx=rt_muldiv((b->c-a->c)*(c->y-a->y)-(c->c-a->c)*(b->y-a->y),64,area);
        cy=rt_muldiv((b->x-a->x)*(c->c-a->c)-(c->x-a->x)*(b->c-a->c),64,area);
    }
#if defined(RT_HOST_TEST) || defined(RT_PM)
    if(rt_occlusion && hidden_triangle(a,b,c,qx,qy,miny,maxy,decal)) return;
    if(rt_visible_spans) {
        if(surface_count==QUEUE_LIMIT) flush_surfaces();
        current_surface=++surface_count;
        surfaces[current_surface].x=cx;surfaces[current_surface].y=cy;
        surfaces[current_surface].origin=(long)((unsigned long)a->c*64-(unsigned long)cx*a->x-(unsigned long)cy*a->y+(cx+cy)/2);
    }
#endif
#if !defined(RT_HOST_TEST) && !defined(RT_PM)
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
    z=(long)((unsigned long)a->z*64-(unsigned long)qx*a->x+
             (unsigned long)qy*(miny-a->y)+(qx+qy)/2);
    shade=(long)((unsigned long)a->c*64-(unsigned long)cx*a->x+
                 (unsigned long)cy*(miny-a->y)+(cx+cy)/2);
    for(y=miny;y<maxy;y++,z=(long)((unsigned long)z+qy),
        shade=(long)((unsigned long)shade+cy)) {
        left=(int)((lx[y]+32767L)>>16);right=(int)((rx[y]+32767L)>>16);
        lx[y]=left;rx[y]=right;
        if(left>=right) continue;
        /* Unsigned intermediates make cancellation well-defined even for a
         * thin triangle whose extrapolated plane exceeds signed 32 bits. */
        qstart[y]=(long)((unsigned long)z+(unsigned long)qx*left);
        cstart[y]=(long)((unsigned long)shade+(unsigned long)cx*left);
    }
#if !defined(RT_HOST_TEST) && !defined(RT_PM)
    /* These values are invariant across all spans and planes of a triangle. */
    direct_args.video_seg=vramseg;direct_args.decal=decal;
    direct_args.dz=(unsigned long)qx*4;direct_args.dcolor=(unsigned long)cx*4;
#endif
    /* Select each VGA plane once per triangle, reusing scanline gradients. */
    for(plane=0;plane<4;plane++) {
#ifdef RT_PM
        if(!rt_ram_color) outpw(0x3c4,0x0002|(0x0100<<plane));
#elif !defined(RT_HOST_TEST)
        outpw(0x3c4,0x0002|(0x0100<<plane));
#endif
        for(y=miny;y<maxy;y++)
            if(lx[y]<rx[y]) span(y,(int)lx[y],(int)rx[y],qstart[y],qx,cstart[y],cx,decal,plane);
    }
}
#if defined(RT_HOST_TEST) || defined(RT_PM)
static void flush_surfaces(void) {
    int y,x,end,plane;unsigned id,index;long shade,step;
    for(y=clip_top;y<clip_bottom;y++) for(x=clip_left;x<clip_right;) {
        id=owners[y*320+x];if(!id) { x++;continue; }
        end=x+1;while(end<clip_right && owners[y*320+end]==id) end++;
        step=surfaces[id].x;
        shade=(long)((unsigned long)surfaces[id].origin+(unsigned long)step*x+(unsigned long)surfaces[id].y*y);
        for(;x<end;x++,shade=(long)((unsigned long)shade+step)) {
#ifdef RT_HOST_TEST
            test_color[y*320+x]=(unsigned char)(shade>>6);
#elif defined(RT_PM)
            plane=x&3;index=y*80+(x>>2);
            if(rt_ram_color) rt_color[plane*16000+index]=(unsigned char)(shade>>6);
            else { outpw(0x3c4,2|(0x100<<plane));rt_video[index]=(unsigned char)(shade>>6); }
#endif
        }
    }
    memset(owners,0,64000*sizeof(*owners));surface_count=0;
}
void rt_depth_flush(void) {
    unsigned i;int top;
    if(queued) {
        flushing=1;
        /* Horizontal tiles retain triangle submission order (including equal
         * depth ties), and reuse original edge equations without reclipping. */
        for(top=clip_top;top<clip_bottom;top+=16) {
            band_top=top;band_bottom=top+16;if(band_bottom>clip_bottom) band_bottom=clip_bottom;
            for(i=0;i<queued;i++) triangle(&triangle_queue[i].v[0],&triangle_queue[i].v[1],&triangle_queue[i].v[2],triangle_queue[i].decal);
        }
        queued=0;flushing=0;band_top=0;band_bottom=200;
    }
    if(rt_visible_spans && surface_count) flush_surfaces();
    detail_flush();
}
#else
void rt_depth_flush(void) { }
#endif
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
#ifdef RT_PM
    rt_clipped++;
#endif
    memcpy(a,vertices,n*sizeof(rt_vertex));
    n=clip(a,b,n,0,clip_left,0);if(n<3) return;
    n=clip(b,a,n,0,clip_right,1);if(n<3) return;
    n=clip(a,b,n,1,clip_top,0);if(n<3) return;
    n=clip(b,a,n,1,clip_bottom,1);if(n<3) return;
    for(i=1;i<n-1;i++) triangle(&a[0],&a[i],&a[i+1],decal);
}

#include "detail_aa.h"
