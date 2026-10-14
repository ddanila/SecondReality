/* DOS/32A flat-memory platform. The resident DIS/STMIK player stays in real
 * mode; only frame-boundary queries cross the DPMI bridge. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dos.h>
#include <i86.h>
#include <conio.h>
#include "pm.h"
#include "pm_tangent.h"
long projclipx[2]={0,319},projclipy[2]={25,174},projclipz[2]={512,9999999};
long projmulx=250,projmuly=220,projaddx=159,projaddy=99;
unsigned char *rt_video=(unsigned char *)0xa0000;
unsigned char rt_color[64000];
int rt_ram_color=1;
unsigned long rt_frames,rt_triangles,rt_spans,rt_vertices,rt_clipped;
#pragma pack(push,1)
typedef struct { unsigned long edi,esi,ebp,reserved,ebx,edx,ecx,eax;
    unsigned short flags,es,ds,fs,gs,ip,cs,sp,ss; } rm_regs;
#pragma pack(pop)
static void real_interrupt(unsigned vector,rm_regs *r) {
    union REGS in,out;
    struct SREGS segments;
    if(vector==0xfc) {
        const unsigned short *entry=(const unsigned short *)(0xfc*4);
        const unsigned short *signature=(const unsigned short *)((unsigned)entry[1]*16+entry[0]-4);
        if(entry[0]<4 || signature[0]!=0x0fc0 || signature[1]!=0x0fc0) {
            puts("Run RT1715.EXE, not U2E.EXE directly.");exit(3);
        }
    }
    memset(&in,0,sizeof(in));segread(&segments);
    in.w.ax=0x300;in.h.bl=vector;in.x.edi=(unsigned)r;
    segments.es=segments.ds;r->flags=0x200;
    int386x(0x31,&in,&out,&segments);
    if(out.x.cflag) { puts("DPMI real-mode interrupt failed");exit(3); }
}
unsigned rt_dis(unsigned service) {
    rm_regs r;memset(&r,0,sizeof(r));r.ebx=service;real_interrupt(0xfc,&r);
    return r.eax&65535;
}
unsigned rt_snapshot(unsigned *ticks) {
    rm_regs r;memset(&r,0,sizeof(r));r.ebx=11;real_interrupt(0xfc,&r);
    if((r.ecx&65535)!=0x1715) { puts("RT1715 protected-mode bridge missing");exit(3); }
    *ticks=r.edx&65535;return r.eax&65535;
}
void rt_wait(void) { rt_dis(1); }
void rt_palette(const unsigned char *p) {
    unsigned i;outp(0x3c8,0);for(i=0;i<768;i++) outp(0x3c9,p[i]);
}
void rt_video_init(void) {
    rm_regs r;memset(&r,0,sizeof(r));r.eax=0x13;real_interrupt(0x10,&r);
    outpw(0x3c4,0x0604);outpw(0x3c4,0x0f02);
    outp(0x3ce,5);outp(0x3cf,inp(0x3cf)&~0x10);
    outp(0x3ce,6);outp(0x3cf,inp(0x3cf)&~2);
    outp(0x3d4,0x14);outp(0x3d5,inp(0x3d5)&~0x40);
    outp(0x3d4,0x17);outp(0x3d5,inp(0x3d5)|0x40);
    memset((void *)0xa0000,0,65536);
}
void rt_draw_page(unsigned page) { rt_video=(unsigned char *)(0xa0000+page*16384); }
void rt_show_page(unsigned page) { outpw(0x3d4,0x0c|(page*0x4000)); }
void rt_color_begin(void) {
    if(rt_ram_color) memset(rt_color,255,sizeof(rt_color));
    else { outpw(0x3c4,0x0f02);memset(rt_video,255,16000); }
}
void rt_color_flush(void) {
    unsigned plane;
    if(rt_ram_color) for(plane=0;plane<4;plane++) {
        outpw(0x3c4,2|(0x100<<plane));
        rt_upload32(rt_video,rt_color+plane*16000,16000);
    }
}
void rt_camera(unsigned angle) {
    unsigned half=angle/2;
    if(half<512) half=512;if(half>16383) half=16383;
    projmulx=((projclipx[1]-projaddx)*rt_tangent[half>>6])>>8;
    projmuly=(projmulx*225)>>8;
}
void calc_rotate(int count,vlist *out,const vlist *in,const rmatrix *r) {
    int i;long m[9];
    for(i=0;i<9;i++) m[i]=(short)r->m[i];
    for(i=0;i<count;i++) {
        out[i].x=rt_dot14(m,&in[i].x)+r->x;
        out[i].y=rt_dot14(m+3,&in[i].x)+r->y;
        out[i].z=rt_dot14(m+6,&in[i].x)+r->z;
        out[i].normal=in[i].normal;
    }
}
void calc_nrotate(int count,nlist *out,const nlist *in,const rmatrix *r) {
    int i,k;long xyz[3],m[9];
    for(k=0;k<9;k++) m[k]=(short)r->m[k];
    for(i=0;i<count;i++) {
        xyz[0]=in[i].x;xyz[1]=in[i].y;xyz[2]=in[i].z;
        out[i].x=(short)rt_dot14(m,xyz);
        out[i].y=(short)rt_dot14(m+3,xyz);
        out[i].z=(short)rt_dot14(m+6,xyz);
    }
}
void calc_applyrmatrix(rmatrix *out,const rmatrix *r) {
    rmatrix old=*out;int row,col;unsigned long sum;
    /* Original matrix composition wraps the 32-bit sum before shifting. */
    for(row=0;row<3;row++) for(col=0;col<3;col++) {
        sum=(unsigned long)r->m[row*3]*old.m[col]+
            (unsigned long)r->m[row*3+1]*old.m[col+3]+
            (unsigned long)r->m[row*3+2]*old.m[col+6];
        out->m[row*3+col]=(long)sum>>14;
    }
    out->x=rt_dot14(r->m,&old.x)+r->x;
    out->y=rt_dot14(r->m+3,&old.x)+r->y;
    out->z=rt_dot14(r->m+6,&old.x)+r->z;
}
long calc_singlez(int index,const vlist *v,const rmatrix *r) {
    return rt_dot14(r->m+6,&v[index].x)+r->z;
}
int rt_project(int count,pvlist *out,rt_vertex *screen,const vlist *v) {
    int i;unsigned all=65535,flags;long z,x,y;
    rt_vertices+=count;
    for(i=0;i<count;i++) {
        z=v[i].z;flags=0;
        if(z<512) { flags|=16;z=512; }
        if(z>projclipz[1]) flags|=32;
        x=rt_muldiv(v[i].x,projmulx,z)+projaddx;
        y=rt_muldiv(v[i].y,projmuly,z)+projaddy;
        if(x<projclipx[0]) flags|=4;if(x>projclipx[1]) flags|=8;
        if(y<projclipy[0]) flags|=1;if(y>projclipy[1]) flags|=2;
        out[i].x=screen[i].x=x;out[i].y=screen[i].y=y;
        out[i].vf=flags;all&=flags;
        if(!(flags&16)) screen[i].z=33553920L/z;
    }
    return all;
}
