/* Original TUN10 ring path and 1060-frame duration, cable conductor grouping. */
#include <dos.h>
#include <conio.h>
#include <string.h>
#include <stdlib.h>
#include "dis.h"
extern short far ringxy[138][64][2];
extern short far motion[6146];
typedef struct {short x,y; unsigned char color;} Ring;
static Ring rings[103];
static unsigned oldpos[77*64];
static unsigned char valid[77*64];
static unsigned char far screen[64000];
static unsigned char far *vram=screen;
/* A visible sheath and cut face establish the cable before entering it. */
static int ux[16]={256,237,181,98,0,-98,-181,-237,-256,-237,-181,-98,0,98,181,237};
static int uy[16]={0,98,181,237,256,237,181,98,0,-98,-181,-237,-256,-237,-181,-98};
static void pixel(int x,int y,int c) {if(x>=0&&x<320&&y>=0&&y<200)vram[(unsigned)y*320+x]=c;}
static void line(int x,int y,int xx,int yy,int c) {
    int dx=abs(xx-x),sx=x<xx?1:-1,dy=-abs(yy-y),sy=y<yy?1:-1,e=dx+dy,t;
    for(;;){pixel(x,y,c);if(x==xx&&y==yy)break;t=e*2;if(t>=dy){e+=dy;x+=sx;}if(t<=dx){e+=dx;y+=sy;}}
}
static void circle(int x,int y,int r,int c) {
    int i,j;for(i=0;i<16;i++){j=(i+1)&15;line(x+(long)ux[i]*r/256,y+(long)uy[i]*r/256,x+(long)ux[j]*r/256,y+(long)uy[j]*r/256,c);}
}
static void disc(int x,int y,int r,int c) {
    int dx,dy,left,right,row;
    for(dy=-r;dy<=r;dy++) {
        row=y+dy;if(row<0||row>199)continue;
        dx=r;while(dx*dx+dy*dy>r*r)dx--;
        left=x-dx;right=x+dx;if(left<0)left=0;if(right>319)right=319;
        if(left<=right)_fmemset(vram+(unsigned)row*320+left,c,right-left+1);
    }
}
static void cutaway(unsigned frame) {
    int i,x,y,r=56+frame/4,cx=205,cy=100;
    if(frame>160)return;
    for(y=cy-r;y<=cy+r;y++)line(0,y,cx,y,2);
    line(0,cy-r,cx,cy-r,5);line(0,cy+r,cx,cy+r,5);
    disc(cx,cy,r,5);disc(cx,cy,r-4,1);
    for(i=0;i<8;i++) {
        x=cx+(long)ux[i*2]*(r*2/3)/256;y=cy+(long)uy[i*2]*(r*2/3)/256;
        disc(x,y,r/6,6+i%3);disc(x,y,r/10,9);
        circle(x,y,r/10,10);
    }
}
static void palette(void) {
    unsigned i,k,light;
    outp(0x3c8,0);
    for(i=0;i<256;i++) {
        light=i<64?0:((i&63)*3/4+12);
        for(k=0;k<3;k++) {
            unsigned c;
            if(i<128) c=k==1?light:light/4;
            else c=k==0?light:(k==1?light*3/4:light/8);
            if(i>0&&i<11) {
                static unsigned char material[10][3]={{3,4,4},{10,11,12},{15,16,17},{22,23,24},{31,32,33},{16,35,18},{35,18,12},{15,23,42},{48,30,12},{63,47,23}};
                c=material[i-1][k];
            }
            outp(0x3c9,c>63?63:c);
        }
    }
}
int main(void) {
    unsigned frame=0,sx=0,sy=0,step,ticks,i,j,index;
    int depth,x,y,dx,dy,radius,color;
    dis_partstart();
    _asm mov ax,13h
    _asm int 10h
    palette();
    dis_waitb();
    while(!dis_exit() && frame<=1060) {
        ticks=dis_waitb();
        _fmemset(vram,0,64000U);
        index=0;
        for(depth=80;depth>=4;depth--) {
            dx=rings[depth].x-rings[5].x;
            dy=rings[depth].y-rings[5].y;
            radius=16384/(depth*7+95);
            color=rings[depth].color+(depth*10+6)/13;
            if(color<64)continue;
            if(depth%8==0)circle(160+dx,100+dy,radius,4);
            for(j=0;j<64;j++,index++) {

                x=ringxy[radius][j][0]+dx;y=ringxy[radius][j][1]+dy;
                valid[index]=(x>=0 && x<320 && y>=0 && y<200);
                if(valid[index]) {oldpos[index]=(unsigned)y*320+x;vram[oldpos[index]]=color;}
            }
        }
        cutaway(frame);
        _fmemcpy((unsigned char far *)0xa0000000UL,screen,64000U);
        for(step=0;step<ticks && frame<=1060;step++) {
            rings[100].x=motion[4097+(sy&2047)]-motion[(sy*3)&4095]-motion[4097+(sx&2047)];
            rings[100].y=motion[(sx*2)&4095]-motion[4097+(sx&2047)]+motion[0];
            memmove(rings,rings+1,100*sizeof(Ring));sx++;sy++;
            rings[99].color=(dis_musrow(0)&7)==0?128:64;
            if(frame>=958)rings[99].color=0;
            frame++;
        }
    }
    return 0;
}
