/* Object transforms and material shading feeding the depth rasterizer. */
#include <stdlib.h>
#include <string.h>
#ifdef RT_PM
#include "pm.h"
#else
#include "CD.H"
#include "C.H"
#endif
#include "depth.h"
#include "lighting.h"
static vlist vertices[500];
static pvlist projected[500];
static nlist normals[500];
static rt_vertex screen[500];
static unsigned key_opacity,boot_opacity=255;
/* Authored 70 Hz timeline: glass warms as the camera first reaches the CRT
 * at 31.4..32.1 s; loader phosphor rises over 31.6..32.3 s. */
void rt_presentation_frame(int frame) {
    rt_crt_brightness=frame<=2198?0:(frame>=2247?255:(frame-2198)*255/49);
    boot_opacity=frame<=2212?0:(frame>=2261?255:(frame-2212)*255/49);
}
static int boot,glass,rounded_key,drone,bezel,detail;
static long mix(long a,long b,long numerator,long denominator) {
    return a+rt_muldiv(b-a,numerator,denominator);
}
#ifdef RT_PM
typedef unsigned short rt_face_word;
#else
typedef int rt_face_word;
#endif
static void polygon(object *o,rt_face_word *face,int decal) {
    rt_vertex a[16],b[16],v,w,t,lo,hi;
    int n=face[0]&255,i,m=0,inside,previous,index,all_inside=1,flat_color;
    long d,num;
    int filtered=(decal || detail) && rt_detail_enabled();
    int readable=drone?2:(rounded_key && face[1]==32?1:0);
    if(filtered) rt_detail_opacity(rounded_key?key_opacity:(boot?boot_opacity:255));
    if(n>8) exit(3);
    flat_color=face[1];
    if(!(face[0]&F_GOURAUD)) flat_color+=rt_readable_shade(rt_shade(&normals[face[2]],face[0]),&normals[face[2]],face[0],readable);
    if(rounded_key && decal) flat_color=face[1]+15;
    /* Most polygons never cross the near plane. Send projected vertices
     * straight to the rasterizer instead of constructing and copying a
     * second camera-space polygon for every key face and ink triangle. */
    if(bezel && !(face[0]&F_GOURAUD)) {
        int shade=flat_color-face[1];
        flat_color=face[1]+(shade>5?shade-5:0);
    }
    for(i=0;i<n;i++) if(vertices[face[i+3]].z<512) { all_inside=0;break; }
    if(all_inside) {
        for(i=0;i<n;i++) {
            index=face[i+3];b[i]=screen[index];
            if(filtered) {
                b[i].x=rt_muldiv(vertices[index].x,projmulx*16,vertices[index].z)+projaddx*16;
                b[i].y=rt_muldiv(vertices[index].y,projmuly*16,vertices[index].z)+projaddy*16;
            }
            b[i].c=(face[0]&F_GOURAUD)?face[1]+(glass?rt_glass_shade_cached(normals,o->v0[index].normal):bezel?rt_bezel_shade_cached(normals,o->v0[index].normal,face[0]):rt_readable_shade(rt_shade_cached(normals,o->v0[index].normal,face[0]),&normals[o->v0[index].normal],face[0],readable)):flat_color;
        }
        if(filtered)rt_detail_raster(b,n);else rt_raster(b,n,decal);return;
    }
    for(i=0;i<n;i++) {
        index=face[i+3];a[i].x=vertices[index].x;a[i].y=vertices[index].y;a[i].z=vertices[index].z;
        a[i].c=(face[0]&F_GOURAUD)?face[1]+(glass?rt_glass_shade_cached(normals,o->v0[index].normal):bezel?rt_bezel_shade_cached(normals,o->v0[index].normal,face[0]):rt_readable_shade(rt_shade_cached(normals,o->v0[index].normal,face[0]),&normals[o->v0[index].normal],face[0],readable)):flat_color;
    }
    v=a[n-1];previous=v.z>=512;
    for(i=0;i<n;i++) {
        w=a[i];inside=w.z>=512;
        if(inside!=previous) {
            lo=v.z<w.z?v:w;hi=v.z<w.z?w:v;
            d=hi.z-lo.z;num=512-lo.z;
            t.x=mix(lo.x,hi.x,num,d);t.y=mix(lo.y,hi.y,num,d);
            t.c=mix(lo.c,hi.c,num,d);t.z=512;b[m++]=t;
        }
        if(inside) b[m++]=w;
        v=w;previous=inside;
    }
    if(m<3) return;
    for(i=0;i<m;i++) {
        b[i].x=rt_muldiv(b[i].x,projmulx*(filtered?16:1),b[i].z)+projaddx*(filtered?16:1);
        b[i].y=rt_muldiv(b[i].y,projmuly*(filtered?16:1),b[i].z)+projaddy*(filtered?16:1);
        b[i].z=33553920L/b[i].z;
    }
    if(filtered)rt_detail_raster(b,m);else rt_raster(b,m,decal);
}
void rt_begin(void) {
    rt_depth_window((int)projclipx[0],(int)projclipx[1]+1,(int)projclipy[0],(int)projclipy[1]+1);
    rt_depth_begin();
}
void rt_flush(void) { }
void rt_queue(object *o) {
    int i,j,n,offset,clip,key,ink,coarse=0,coarse_vertices,coarse_faces;
    rt_face_word *face;
    vlist *v;nlist *normal;
    long nearest=0x7fffffffL,facing;
    if(!(o->flags&F_VISIBLE)) return;
    if(o->vnum>500 || o->nnum>500) exit(3);
    o->v=vertices;o->pv=projected;o->n=normals;
    key=!strncmp(o->name,"\"key-",5);
    ink=!strncmp(o->name,"\"ink-",5);
    detail=!strncmp(o->name,"\"monitor-vents",14);
    boot=!strncmp(o->name,"\"ink-boot-",10);
    glass=!strcmp(o->name,"\"screen\"");
    bezel=!strcmp(o->name,"\"bezel\"");
    rounded_key=!strncmp(o->name,"\"key-r-",7);
    drone=!strcmp(o->name,"\"s01\"");
    coarse_vertices=rounded_key?16:8;coarse_faces=rounded_key?14:6;
    if(key) {
        calc_rotate(coarse_vertices,vertices,o->v0,o->r);
        for(i=0;i<coarse_vertices;i++) if(vertices[i].z<nearest) nearest=vertices[i].z;
        coarse=nearest>240L*64L;
        /* Fade ink before the geometry LOD drops its legend faces. */
        key_opacity=nearest<=160L*64L?255:(nearest>=240L*64L?0:
            (unsigned)((240L*64L-nearest)*255/(80L*64L)));
#ifdef RT_PM
        /* One-millimetre dish detail must be subpixel. Per-object hysteresis
         * prevents switching back and forth during slow camera motion. */
        if(rt_screen_lod) {
            long limit=projmuly*64L*100L;
            if(nearest<=512) o->lod=0;
            else if(o->lod) { if(nearest*125L<limit) o->lod=0; }
            else if(nearest*100L>limit) o->lod=1;
            coarse=o->lod;
        }
#endif
    }
#ifdef RT_PM
    if(coarse) {
        if(rt_project(coarse_vertices,projected,screen,vertices)) return;
    } else {
        rt_vertices+=o->vnum;
        if(rt_transform_project(o->vnum,vertices,o->v0,o->r,projected,screen)) return;
    }
    calc_nrotate(coarse?coarse_faces:o->nnum,normals,o->n0,o->r);
#else
    if(!coarse) calc_rotate(o->vnum,vertices,o->v0,o->r);
    calc_nrotate(coarse?coarse_faces:o->nnum,normals,o->n0,o->r);
    if(calc_project(coarse?coarse_vertices:o->vnum,projected,vertices)) return;
    for(i=0;i<(coarse?coarse_vertices:o->vnum);i++) if(vertices[i].z>=512) {
        screen[i].x=rt_muldiv(vertices[i].x,projmulx,vertices[i].z)+projaddx;
        screen[i].y=rt_muldiv(vertices[i].y,projmuly,vertices[i].z)+projaddy;
        screen[i].z=33553920L/vertices[i].z;
    }
#endif
    rt_light_begin();
    n=o->pl[0][0]-3;
    for(i=key && !coarse?coarse_faces:0;i<(coarse?coarse_faces:n);i++) {
        offset=o->pl[0][i+2];face=(rt_face_word *)(o->pd+offset);
        clip=31;
        for(j=0;j<(face[0]&255);j++) clip&=projected[face[j+3]].vf;
        if(clip) continue;
        v=&vertices[face[3]];normal=&normals[face[2]];
        facing=(v->x/16)*normal->x+(v->y/16)*normal->y+(v->z/16)*normal->z;
        if(!(face[0]&F_2SIDE) && facing>=0) continue;
        polygon(o,face,ink || (key && (face[1]==96 || (rounded_key && face[1]==144))));
    }
}
