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

/* Broad view-dependent sheen on curved CRT glass. The glow floor and small
 * highlight stay in the screen's own 16-color ramp; no drone colors change. */
static int rt_glass_shade_cached(nlist *normals,unsigned index) {
    long light,power;int value;
    if(rt_light_stamps[index]!=rt_light_epoch || rt_light_modes[index]!=4) {
        light=((long)normals[index].x*-6000L+(long)normals[index].y*-7000L+
               (long)normals[index].z*-13300L)>>14;
        if(light<0) light=0;if(light>16384) light=16384;
        /* A broad quadratic reflection replaces the steep power-16 spot.
         * Sum before quantizing: no separate half-light threshold on glass. */
        power=(light*light)>>14;
        /* Leave guard shades at both ramp edges: fixed-point Gouraud
         * interpolation on thin projected triangles can extrapolate by a
         * shade. Index 63 belongs to beige paint, not the green CRT ramp. */
        value=2+(int)((light*5+power*6)>>14);
        rt_light_values[index]=(unsigned char)value;rt_light_modes[index]=4;
        rt_light_stamps[index]=rt_light_epoch;
    }
    return rt_light_values[index];
}

/* Local readability adjustments; never escape an object's original ramp.
 * kind 1 is charcoal key plastic; kind 2 is the original drone. */
static int rt_readable_shade(int value,nlist *normal,int flags,int kind) {
    int mode=(flags&0x0c00)>>10,maximum;
    if(!mode) return value;
    if(kind==1) return 1+value*5/15;
    if(kind==2) {
        maximum=(1<<(mode+2))-1;
        value+=1+(normal->z>-8000 && normal->z<8000?2:0);
        if(value>maximum)value=maximum;
    }
    return value;
}

#endif
