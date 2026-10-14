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
void rt_raster(rt_vertex *vertices,int count,int decal);
#endif
