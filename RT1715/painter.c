/* Object transforms and material shading feeding the EMS depth rasterizer. */
#include <stdlib.h>
#include <string.h>
#include "CD.H"
#include "C.H"
#include "depth.h"
static vlist vertices[500];
static pvlist projected[500];
static nlist normals[500];
static rt_vertex screen[500];
static long mix(long a,long b,long numerator,long denominator) {
    return a+rt_muldiv(b-a,numerator,denominator);
}
static int shade(nlist *normal,int flags) {
    long light;
    int mode=(flags&0x0c00)>>10,value;
    if(!mode) return 0;
    light=(long)normal->x*12118L+(long)normal->y*10603L+(long)normal->z*3030L;
    value=(int)(light>>21)+128;if(value<0) value=0;if(value>255) value=255;
    value>>=6-mode;if(value<1) value=1;if(value>30) value=30;
    return value;
}
static void polygon(object *o,int *face,int decal) {
    rt_vertex a[16],b[16],v,w,t,lo,hi;
    int n=face[0]&255,i,m=0,inside,previous,index,all_inside=1,flat_color;
    long d,num;
    if(n>8) exit(3);
    flat_color=face[1];
    if(!(face[0]&F_GOURAUD)) flat_color+=shade(&normals[face[2]],face[0]);
    for(i=0;i<n;i++) {
        index=face[i+3];a[i].x=vertices[index].x;a[i].y=vertices[index].y;a[i].z=vertices[index].z;
        if(a[i].z<512) all_inside=0;
        a[i].c=(face[0]&F_GOURAUD)?face[1]+shade(&normals[o->v0[index].normal],face[0]):flat_color;
    }
    if(all_inside) {
        for(i=0;i<n;i++) { b[i]=screen[face[i+3]];b[i].c=a[i].c; }
        rt_raster(b,n,decal);return;
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
        b[i].x=rt_muldiv(b[i].x,projmulx,b[i].z)+projaddx;
        b[i].y=rt_muldiv(b[i].y,projmuly,b[i].z)+projaddy;
        b[i].z=33553920L/b[i].z;
    }
    rt_raster(b,m,decal);
}
void rt_begin(void) {
    rt_depth_window((int)projclipx[0],(int)projclipx[1]+1,(int)projclipy[0],(int)projclipy[1]+1);
    rt_depth_begin();
}
void rt_flush(void) { }
void rt_queue(object *o) {
    int i,j,n,offset,*face,clip,key,coarse=0;
    vlist *v;nlist *normal;
    long nearest=0x7fffffffL,facing;
    if(!(o->flags&F_VISIBLE)) return;
    if(o->vnum>500 || o->nnum>500) exit(3);
    o->v=vertices;o->pv=projected;o->n=normals;
    key=!strncmp(o->name,"\"key-",5);
    if(key) {
        calc_rotate(8,vertices,o->v0,o->r);
        for(i=0;i<8;i++) if(vertices[i].z<nearest) nearest=vertices[i].z;
        coarse=nearest>240L*64L;
    }
    if(!coarse) calc_rotate(o->vnum,vertices,o->v0,o->r);
    calc_nrotate(coarse?6:o->nnum,normals,o->n0,o->r);
    if(calc_project(coarse?8:o->vnum,projected,vertices)) return;
    for(i=0;i<(coarse?8:o->vnum);i++) if(vertices[i].z>=512) {
        screen[i].x=rt_muldiv(vertices[i].x,projmulx,vertices[i].z)+projaddx;
        screen[i].y=rt_muldiv(vertices[i].y,projmuly,vertices[i].z)+projaddy;
        screen[i].z=33553920L/vertices[i].z;
    }
    n=o->pl[0][0]-3;
    for(i=key && !coarse?6:0;i<(coarse?6:n);i++) {
        offset=o->pl[0][i+2];face=(int *)(o->pd+offset);
        clip=31;
        for(j=0;j<(face[0]&255);j++) clip&=projected[face[j+3]].vf;
        if(clip) continue;
        v=&vertices[face[3]];normal=&normals[face[2]];
        facing=(v->x/16)*normal->x+(v->y/16)*normal->y+(v->z/16)*normal->z;
        if(!(face[0]&F_2SIDE) && facing>=0) continue;
        polygon(o,face,key && face[1]==96);
    }
}
