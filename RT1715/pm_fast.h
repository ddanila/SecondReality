#ifndef RT_PM_FAST_H
#define RT_PM_FAST_H
#include <stddef.h>
/* 32-bit near cdecl. No segment windows or bank mapping in these kernels. */
long __cdecl rt_muldiv(long,long,long);
long __cdecl rt_dot14(const long *matrix,const long *xyz);
void __cdecl rt_span32(unsigned short *depth,unsigned char *color,unsigned count,
                      long z,long dz,long shade,long dshade,unsigned decal);
void __cdecl rt_upload32(unsigned char *destination,const unsigned char *source,unsigned bytes);
typedef struct {
    const void *vertices;
    unsigned short *depth;
    unsigned char *color;
    long *left,*right;
    int top,bottom;
    long qx,qy,cx,cy,qorigin,corigin; /* Assembly setup scratch. */
    unsigned decal,ram;
    long area;
} rt_triangle_args;
typedef char rt_triangle_layout[(offsetof(rt_triangle_args,area)==60 && sizeof(rt_triangle_args)==64)?1:-1];
unsigned __cdecl rt_triangle32(rt_triangle_args *args);
#endif
