/* Native host front end for the exact painter. No DOS emulation or build. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "pm.h"
long projclipx[2]={0,319},projclipy[2]={25,174},projclipz[2]={512,9999999};
long projmulx,projmuly,projaddx=159,projaddy=99;
int rt_screen_lod=0,rt_profile=0;
unsigned long rt_vertices;
static long dot(const long *m,const long *v) {
    return (int32_t)(((int64_t)m[0]*v[0]+(int64_t)m[1]*v[1]+(int64_t)m[2]*v[2])>>14);
}
void calc_rotate(int count,vlist *out,const vlist *in,const rmatrix *r) {
    int i;long m[9],v[3];for(i=0;i<9;i++)m[i]=(short)r->m[i];
    for(i=0;i<count;i++) {
        v[0]=in[i].x;v[1]=in[i].y;v[2]=in[i].z;
        out[i].x=(int32_t)(dot(m,v)+r->x);out[i].y=(int32_t)(dot(m+3,v)+r->y);out[i].z=(int32_t)(dot(m+6,v)+r->z);
        out[i].normal=in[i].normal;
    }
}
void calc_nrotate(int count,nlist *out,const nlist *in,const rmatrix *r) {
    int i,k;long m[9],v[3];for(k=0;k<9;k++)m[k]=(short)r->m[k];
    for(i=0;i<count;i++) {
        v[0]=in[i].x;v[1]=in[i].y;v[2]=in[i].z;
        out[i].x=(short)dot(m,v);out[i].y=(short)dot(m+3,v);out[i].z=(short)dot(m+6,v);
    }
}
int rt_project(int count,pvlist *out,rt_vertex *s,const vlist *v) {
    int i;unsigned all=65535,flags;long z,x,y;
    for(i=0;i<count;i++) {
        z=v[i].z;flags=0;if(z<512){flags|=16;z=512;}if(z>projclipz[1])flags|=32;
        x=rt_muldiv(v[i].x,projmulx,z)+projaddx;y=rt_muldiv(v[i].y,projmuly,z)+projaddy;
        if(x<projclipx[0])flags|=4;if(x>projclipx[1])flags|=8;
        if(y<projclipy[0])flags|=1;if(y>projclipy[1])flags|=2;
        out[i].x=s[i].x=x;out[i].y=s[i].y=y;out[i].vf=flags;all&=flags;
        if(!(flags&16))s[i].z=33553920L/z;
    }
    return all;
}
int rt_transform_project(int n,vlist *v,const vlist *in,const rmatrix *r,pvlist *p,rt_vertex *s) {
    calc_rotate(n,v,in,r);return rt_project(n,p,s,v);
}
static void bake_polygon(rt_vertex *,int,int);
static void bake_detail(rt_vertex *,int);
#define rt_raster bake_polygon
#define rt_detail_raster bake_detail
#include "painter.c"
#undef rt_raster
#undef rt_detail_raster
static object *objects[256];
int bake_mesh_lod;
static unsigned char boundary[256][500];
static unsigned short edge_list[256][4096][2],edge_count[256];
static unsigned current_object,current_face;
extern unsigned rt_bake_tag;
void rt_bake_face(unsigned i) {current_face=i;rt_bake_tag=(current_object<<16)|(i+1);}
static unsigned u16(const unsigned char *p){return p[0]+256*p[1];}
static uint32_t u32(const unsigned char *p){return u16(p)+((uint32_t)u16(p+2)<<16);}
void bake_load(unsigned id,const unsigned char *bytes,unsigned size) {
    object *o=calloc(1,sizeof(*o));unsigned char *data=malloc(size),*p,*d;unsigned n,i;
    memcpy(data,bytes,size);objects[id]=o;o->flags=F_VISIBLE;o->r=calloc(1,sizeof(rmatrix));
    for(p=data;p<data+size;p+=8+n) {
        n=u32(p+4);d=p+8;
        if(!memcmp(p,"NAME",4))o->name=(char *)d;
        if(!memcmp(p,"VERT",4)) {
            o->vnum=u16(d);o->v0=calloc(o->vnum,sizeof(vlist));
            for(i=0;i<o->vnum;i++) {o->v0[i].x=(int32_t)u32(d+4+i*16);o->v0[i].y=(int32_t)u32(d+8+i*16);o->v0[i].z=(int32_t)u32(d+12+i*16);o->v0[i].normal=(short)u16(d+16+i*16);}
        }
        if(!memcmp(p,"NORM",4)){o->nnum=u16(d);o->n0=(nlist *)(d+4);}
        if(!memcmp(p,"POLY",4))o->pd=d;
        if(!memcmp(p,"ORD0",4))o->pl[0]=(unsigned short *)d;
    }
    {
        unsigned short *counts=calloc(500*500,sizeof(*counts)),*face;
        unsigned f,k,a,b,j,faces=o->pl[0][0]-3;
        for(f=0;f<faces;f++) {
            face=(unsigned short *)(o->pd+o->pl[0][f+2]);n=face[0]&255;
            for(k=0;k<n;k++){a=face[3+k];b=face[3+(k+1)%n];if(a>b){j=a;a=b;b=j;}counts[a*500+b]++;}
        }
        for(a=0;a<(unsigned)o->vnum;a++)for(b=a+1;b<(unsigned)o->vnum;b++)if(counts[a*500+b]) {
            if(counts[a*500+b]==1)boundary[id][a]=boundary[id][b]=1;
            if(edge_count[id]>=4096)exit(3);
            edge_list[id][edge_count[id]][0]=a;edge_list[id][edge_count[id]++][1]=b;
        }
        free(counts);
    }
}
static FILE *commands;
void bake_begin(int frame,int px,int py,const char *path) {
    projmulx=px;projmuly=py;rt_presentation_frame(frame);rt_begin();
    commands=fopen(path,"wb");if(!commands)exit(3);
}
void bake_object(unsigned id,const long *state) {
    object *o=objects[id];int i;current_object=id;
    o->r->x=state[0];o->r->y=state[1];o->r->z=state[2];for(i=0;i<9;i++)o->r->m[i]=state[i+3];
    if(bake_mesh_lod && (strstr(o->name,"monitor") || strstr(o->name,"screen") || strstr(o->name,"bezel") || strstr(o->name,"src-drive") || strstr(o->name,"fascia") || strstr(o->name,"src-base"))) {
        vlist backup[500],view[500];long px[500],py[500],nearest=0x7fffffffL;
        int k,a,b;long dx,dy,dz;
        memcpy(backup,o->v0,o->vnum*sizeof(*backup));calc_rotate(o->vnum,view,o->v0,o->r);
        for(k=0;k<o->vnum;k++) {
            if(view[k].z<nearest)nearest=view[k].z;
            if(view[k].z<512)continue;
            px[k]=rt_muldiv(view[k].x,projmulx*16,view[k].z);py[k]=rt_muldiv(view[k].y,projmuly*16,view[k].z);
        }
        if(nearest>300*64)for(k=0;k<edge_count[id];k++) {
            a=edge_list[id][k][0];b=edge_list[id][k][1];if(boundary[id][a] || boundary[id][b])continue;
            dx=px[a]-px[b];dy=py[a]-py[b];if(dx*dx+dy*dy>144)continue;
            dx=o->v0[a].x-o->v0[b].x;dy=o->v0[a].y-o->v0[b].y;dz=o->v0[a].z-o->v0[b].z;
            if(dx*dx+dy*dy+dz*dz>640*640)continue;
            o->v0[b].x=o->v0[a].x;o->v0[b].y=o->v0[a].y;o->v0[b].z=o->v0[a].z;
        }
        rt_queue(o);memcpy(o->v0,backup,o->vnum*sizeof(*backup));
    } else rt_queue(o);
}
extern int bake_clip(rt_vertex *,int,rt_vertex *);
static void bake_polygon(rt_vertex *v,int n,int decal) {
    rt_vertex clipped[16];int original=n;
    unsigned i;uint32_t h[3]={rt_bake_tag,n,decal};int32_t vertex[4];
    n=bake_clip(v,n,clipped);h[1]=n;
    if(n>=3) {
    fwrite(h,4,3,commands);
    for(i=0;i<n;i++){vertex[0]=clipped[i].x;vertex[1]=clipped[i].y;vertex[2]=clipped[i].z;vertex[3]=clipped[i].c;fwrite(vertex,4,4,commands);}
    }
    rt_raster(v,original,decal);
}
static void bake_detail(rt_vertex *v,int n){rt_detail_raster(v,n);}
void bake_end(void){fclose(commands);}
