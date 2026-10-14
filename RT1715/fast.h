#ifndef RT_FAST_H
#define RT_FAST_H
/* Stack cdecl, far entry points, DX:AX long return. Keep this ABI explicit:
 * Watcom's default register convention differs from our original C modules.
 * Far buffers must not cross a 64K segment boundary. Copy permits overlap
 * only when destination precedes source, as in animation buffer compaction. */
typedef struct {
    unsigned depth_seg,depth_off,video_seg,video_off,count,decal;
    long z,dz,color,dcolor;
} rt_span_args;
/* divisor != 0; the signed quotient must fit in 32 bits. */
long __far __cdecl rt_muldiv(long a,long b,long divisor);
void __far __cdecl rt_span386(const rt_span_args __far *args);
void __far __cdecl rt_clear386(void __far *destination,unsigned bytes);
void __far __cdecl rt_copy386(void __far *destination,const void __far *source,unsigned bytes);
/* Three vertices, each four longs (x,y,z,color); clipped x/y are bounded by
 * the 320x200 viewport. Initialize and walk all three edges in one call. */
void __far __cdecl rt_edges386(const void __far *vertices,long __far *left,
                             long __far *right,int top,int bottom);
#endif
