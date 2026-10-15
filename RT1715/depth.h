#ifndef RT_DEPTH_H
#define RT_DEPTH_H
#ifdef RT_HOST_TEST
static long rt_muldiv(long a,long b,long d) {
    if(a>=-32767L && a<=32767L && b>=-32767L && b<=32767L)
        return (a*b)/d;
    return (long)(((long long)a*b)/d);
}
#elif defined(RT_PM)
#include "pm_fast.h"
#else
#include "fast.h"
#endif
/* Screen coordinates, reciprocal depth (larger = nearer), palette index. */
typedef struct { long x,y,z,c; } rt_vertex;
void rt_depth_begin(void);
void rt_depth_window(int left,int right,int top,int bottom);
void rt_depth_end(void);
void rt_depth_flush(void);
extern int rt_occlusion,rt_tiles,rt_visible_spans;
extern unsigned long rt_occluded,rt_occlusion_queries;
int rt_detail_enabled(void);
void rt_detail_init(const unsigned char *palette,const unsigned char *lookup);
void rt_detail_masks(const unsigned char *,unsigned);
void rt_detail_raster(rt_vertex *vertices,int count);
void rt_raster(rt_vertex *vertices,int count,int decal);
void rt_presentation_frame(int frame);
void rt_detail_opacity(unsigned opacity);
#endif
