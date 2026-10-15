/* Pose-specific drawing work baked on the host. Bounded block decompression,
 * source/version fingerprints and live fallback; no full-frame video cache. */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dos.h>
#include <stdint.h>
#include "pm.h"
#include "baked.h"
#include "bake_signature.h"
int rt_use_masks=1,rt_use_faces=1,rt_use_projection=1,rt_baked_active;
unsigned long rt_baked_hits,rt_baked_reads,rt_baked_memory;
static FILE *cache;
static uint32_t *offsets,*lengths,*checks;
static unsigned long frames,base,capacity,last=~0UL;
static unsigned char *compressed,*decoded,*polygons,*masks;
static unsigned polygon_count,mask_count;
static unsigned char face_bits[256][64];
static unsigned word(const unsigned char *p){return p[0]|((unsigned)p[1]<<8);}
static unsigned long dword(const unsigned char *p){return word(p)|((unsigned long)word(p+2)<<16);}
#include "bake_codec.h"
static void disable(void) {
    if(cache)fclose(cache);cache=0;rt_baked_active=0;last=~0UL;
    rt_baked_memory=0;
    free(offsets);offsets=0;free(compressed);compressed=0;free(decoded);decoded=0;
}
void rt_baked_close(void){disable();}
void rt_baked_init(unsigned long hash,unsigned objects) {
    unsigned attributes;unsigned char h[24];long size;unsigned i;unsigned long total;
    if(_dos_getfileattr("U2E.BKC",&attributes) || (attributes&0x10))return;
    cache=fopen("U2E.BKC","rb");if(!cache)return;
    fseek(cache,0,SEEK_END);size=ftell(cache);rewind(cache);
    if(fread(h,1,24,cache)!=24 || memcmp(h,"BKC1",4) || dword(h+4)!=RT_BAKE_SIGNATURE || dword(h+8)!=hash || dword(h+16)!=objects){disable();return;}
    frames=dword(h+12);capacity=dword(h+20);
    if(!frames || frames>4096 || capacity<12 || capacity>1048576){disable();return;}
    base=28+frames*12;total=(frames*3+1)*4;
    rt_baked_memory=total+capacity*2+capacity/255+32+sizeof(face_bits);
    if(size<(long)base){disable();return;}
    offsets=malloc(total);compressed=malloc(capacity+capacity/255+32);decoded=malloc(capacity);
    if(!offsets || !compressed || !decoded){disable();return;}
    if(fread(offsets,1,total,cache)!=total){disable();return;}
    lengths=offsets+frames+1;checks=lengths+frames;
    if(offsets[0] || offsets[frames]!=(unsigned long)size-base){disable();return;}
    for(i=0;i<frames;i++)if(offsets[i]>offsets[i+1] || offsets[i+1]>offsets[frames] ||
        offsets[i+1]-offsets[i]>capacity+capacity/255+32 || lengths[i]>capacity){disable();return;}
}
void rt_baked_forget(void){last=~0UL;}
int rt_baked_prepare(unsigned frame) {
    unsigned long size,n,tag,h=2166136261UL;unsigned i,j,p,previous=0,coverage=0;
    unsigned char *at,*end;
    rt_baked_active=0;
    if(!cache || !rt_ram_color || !rt_detail_enabled() || frame>=frames || !(rt_use_masks || rt_use_faces || rt_use_projection))return 0;
    if(last==frame){rt_baked_active=1;rt_baked_hits++;return 1;}
    size=offsets[frame+1]-offsets[frame];if(!size)return 0;
    if(fseek(cache,base+offsets[frame],SEEK_SET) || fread(compressed,1,size,cache)!=size ||
        !rt_unpack_block(compressed,size,decoded,lengths[frame])){disable();return 0;}
    rt_baked_reads+=size;
    for(i=0;i<lengths[frame];i++)h=(uint32_t)((h^decoded[i])*16777619UL);
    if(h!=checks[frame] || lengths[frame]<12){disable();return 0;}
    at=decoded;end=decoded+lengths[frame];n=dword(at);polygon_count=dword(at+4);mask_count=dword(at+8);at+=12;
    if(n>(unsigned long)(end-at)/4){disable();return 0;}
    memset(face_bits,0,sizeof(face_bits));
    for(i=0;i<n;i++) {
        tag=dword(at);at+=4;p=tag>>16;j=(tag&65535)-1;
        if(!p || p>=256 || j>=512){disable();return 0;}
        face_bits[p][j>>3]|=1<<(j&7);
    }
    polygons=at;
    for(i=0;i<polygon_count;i++) {
        if(end-at<2 || at[0]<3 || at[0]>12 || at[1]>1 || end-at<2+7*at[0]){disable();return 0;}
        at+=2+7*at[0];
    }
    masks=at;if(mask_count>(unsigned long)(end-at)/8 || end-at!=mask_count*8){disable();return 0;}
    for(i=0;i<mask_count;i++,at+=8) {
        p=word(at);j=word(at+2);if(p>=64000 || !j || (i && p<previous)){disable();return 0;}
        if(!i || p!=previous)coverage=0;if(coverage&j){disable();return 0;}coverage|=j;previous=p;
    }
    last=frame;rt_baked_active=1;rt_baked_hits++;return 1;
}
int rt_baked_face(unsigned object,unsigned face) {
    if(!rt_baked_active || !rt_use_faces)return 1;
    return object<256 && face<512 && (face_bits[object][face>>3]&(1<<(face&7)));
}
void rt_baked_draw(void) {
    unsigned char *at=polygons;rt_vertex v[12];unsigned i,j,n,decal;
    for(i=0;i<polygon_count;i++) {
        n=*at++;decal=*at++;
        for(j=0;j<n;j++,at+=7){v[j].x=(short)word(at);v[j].y=(short)word(at+2);v[j].z=word(at+4);v[j].c=at[6];}
        rt_raster(v,n,decal);
    }
}
void rt_baked_finish(void) {if(rt_baked_active && rt_use_masks)rt_detail_masks(masks,mask_count);}
