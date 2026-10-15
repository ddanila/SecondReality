#ifndef RT_PM_H
#define RT_PM_H
#include <stdint.h>
#include <stddef.h>
#include "depth.h"
typedef struct { long m[9],x,y,z; } rmatrix;
/* The asset format is 16-bit regardless of the compiler's int width. */
typedef struct { long x,y,z; short normal,reserved; } vlist;
typedef struct { short x,y,z,reserved; } nlist;
typedef struct { long x,y; unsigned vf; } pvlist;
typedef struct object {
    int flags,vnum,nnum,nnum1,lod;
    rmatrix *r,*r0;
    unsigned char *pd;
    unsigned short *pl[16];
    vlist *v0,*v;
    nlist *n0,*n;
    pvlist *pv;
    char *name;
    long bounds_min[3],bounds_max[3];
} object;
#define F_VISIBLE 1
#define F_2SIDE 0x200
#define F_GOURAUD 0x1000
extern long projclipx[2],projclipy[2],projclipz[2];
extern long projmulx,projmuly,projaddx,projaddy;
extern unsigned char *rt_video;
extern int rt_ram_color;
extern int rt_triangle_kernel,rt_bounds_culling;
extern int rt_screen_lod,rt_profile;
extern unsigned long rt_pixels,rt_pixels_passed;
extern unsigned long rt_objects_tested,rt_objects_rejected;
void rt_bounds_init(object *);
int rt_bounds_outside(const object *);
extern unsigned long rt_frames,rt_triangles,rt_spans,rt_vertices,rt_clipped;
void calc_rotate(int,vlist *,const vlist *,const rmatrix *);
void calc_nrotate(int,nlist *,const nlist *,const rmatrix *);
void calc_applyrmatrix(rmatrix *,const rmatrix *);
long calc_singlez(int,const vlist *,const rmatrix *);
int rt_project(int,pvlist *,rt_vertex *,const vlist *);
int __cdecl rt_transform_project(int,vlist *,const vlist *,const rmatrix *,pvlist *,rt_vertex *);
void rt_camera(unsigned);
void rt_begin(void);
void rt_queue(object *);
unsigned rt_dis(unsigned);
unsigned rt_snapshot(unsigned *ticks);
void rt_wait(void);
void rt_video_init(void);
void rt_palette(const unsigned char *);
void rt_draw_page(unsigned);
void rt_show_page(unsigned);
void rt_color_begin(void);
void rt_color_flush(void);
#endif
