#ifndef RT_LIGHTING_H
#define RT_LIGHTING_H
/* Included after the renderer's nlist definition. The generation changes for
 * every transformed object; normal indices must not leak across objects. */
#include <string.h>
static unsigned rt_light_epoch,rt_light_stamps[500];
static unsigned char rt_light_modes[500],rt_light_values[500];
static void rt_light_begin(void) {
    if(++rt_light_epoch==0) {
        memset(rt_light_stamps,0,sizeof(rt_light_stamps));rt_light_epoch=1;
    }
}
static int rt_shade(nlist *normal,int flags) {
    long light;
    int mode=(flags&0x0c00)>>10,value;
    if(!mode) return 0;
    light=(long)normal->x*12118L+(long)normal->y*10603L+(long)normal->z*3030L;
    value=(int)(light>>21)+128;if(value<0) value=0;if(value>255) value=255;
    value>>=6-mode;if(value<1) value=1;if(value>30) value=30;
    return value;
}
static int rt_shade_cached(nlist *normals,unsigned index,int flags) {
    unsigned mode=(flags&0x0c00)>>10;
    if(rt_light_stamps[index]!=rt_light_epoch || rt_light_modes[index]!=mode) {
        rt_light_values[index]=(unsigned char)rt_shade(&normals[index],flags);
        rt_light_modes[index]=(unsigned char)mode;rt_light_stamps[index]=rt_light_epoch;
    }
    return rt_light_values[index];
}
#endif
