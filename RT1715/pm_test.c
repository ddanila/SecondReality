/* Native 32-bit checks, run under the same extender as the flyover. */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <conio.h>
#include "pm.h"
#include "pm_vectors.h"
#include "pm_raster_cases.h"
unsigned rt_depth_at(int,int);
unsigned rt_color_at(int,int);
static unsigned short depths[320],expected_depth[320];
static unsigned char colors[100],expected_color[100];
static unsigned seed=1715;
static unsigned random32(void) { seed=seed*1664525UL+1013904223UL;return seed; }
static long dot(const long *m,const long *v) {
    return (long)(((long long)m[0]*v[0]+(long long)m[1]*v[1]+(long long)m[2]*v[2])>>14);
}
static void check(int ok,const char *what) { if(!ok) { printf("FAIL %s\n",what);exit(1); } }
static void check_video_pages(void) {
    extern unsigned char rt_color[64000];
    static unsigned char expected[64000];
    unsigned backend,pass,page,plane,i,top,bottom;
    rt_video_init();
    for(backend=0;backend<2;backend++) for(pass=0;pass<4;pass++) {
        rt_ram_color=!backend;top=pass==2?0:25;bottom=pass==2?200:175;
        projclipy[0]=top;projclipy[1]=bottom-1;
        for(page=0;page<4;page++) {
            rt_draw_page(page);rt_color_begin();
            for(plane=0;plane<4;plane++) {
                if(rt_ram_color) memset(rt_color+plane*16000+top*80,10+plane,(bottom-top)*80);
                else { outpw(0x3c4,2|(0x100<<plane));memset(rt_video+top*80,10+plane,(bottom-top)*80); }
            }
            rt_color_flush();
            for(plane=0;plane<4;plane++) {
                outpw(0x3ce,4|(plane<<8));
                for(i=0;i<16000;i++) check(rt_video[i]==(i>=top*80 && i<bottom*80?10+plane:255),"VGA page/viewport borders");
            }
        }
    }
    /* Compare actual direct-VGA assembly writes against the RAM backend. */
    for(i=0;i<8;i++) {
        unsigned x;
        rt_ram_color=1;rt_depth_begin();rt_color_begin();
        rt_raster(raster_cases[i].v,3,raster_cases[i].decal);memcpy(expected,rt_color,sizeof(expected));
        rt_ram_color=0;rt_depth_begin();rt_color_begin();
        rt_raster(raster_cases[i].v,3,raster_cases[i].decal);
        for(plane=0;plane<4;plane++) {
            outpw(0x3ce,4|(plane<<8));
            for(x=0;x<16000;x++) check(rt_video[x]==expected[plane*16000+x],"direct VGA raster matches RAM");
        }
    }
    rt_ram_color=1;
    puts("PASS four VGA pages, repeated clears, viewport changes, RAM/direct and 8 direct raster images");
}
int main(void) {
    unsigned i,j,n,start,plane,bias,depth;long z,dz,c,dc,q,shade,m[3],v[3];
    rmatrix matrix;vlist input[20],output[20];pvlist projected[20];rt_vertex screen[20];
    unsigned char src[263],dest[263];
    for(i=0;i<sizeof(vectors)/sizeof(vectors[0]);i++)
        check(rt_muldiv(vectors[i][0],vectors[i][1],vectors[i][2])==vectors[i][3],"muldiv");
    puts("PASS 2000 signed 64-bit intermediate multiply/divides");
    for(i=0;i<2000;i++) {
        for(j=0;j<3;j++) { m[j]=(short)random32();v[j]=(long)random32(); }
        check(rt_dot14(m,v)==dot(m,v),"dot product");
    }
    puts("PASS 2000 wide dot products, negative shifts and overflow truncation");
    for(i=0;i<800;i++) {
        for(j=0;j<320;j++) depths[j]=expected_depth[j]=(unsigned short)random32();
        memset(colors,0x5a,sizeof(colors));memcpy(expected_color,colors,sizeof(colors));
        plane=random32()&3;start=(random32()%8)*4+plane;n=random32()%64;
        z=(long)(random32()%65536)*64;dz=(long)(random32()%513)-256;
        c=(long)(random32()%200+20)*64;dc=i%4?(long)(random32()%31)-15:0;bias=i&1;
        q=z;shade=c;
        for(j=0;j<n;j++,q+=dz,shade+=dc) {
            depth=(unsigned short)(q>>6);if(bias && depth<65535) depth++;
            if(depth>=expected_depth[start+j*4]) {
                expected_depth[start+j*4]=(unsigned short)depth;expected_color[3+j]=(unsigned char)(shade>>6);
            }
        }
        rt_span32(depths+start,colors+3,n,z,dz,c,dc,bias);
        check(!memcmp(depths,expected_depth,sizeof(depths)),"span depth/guards");
        check(!memcmp(colors,expected_color,sizeof(colors)),"span color/guards");
    }
    puts("PASS 800 spans: flat/smooth, decals, empty spans, wrap and guards");
    memset(&matrix,0,sizeof(matrix));matrix.m[0]=matrix.m[4]=matrix.m[8]=16384;
    matrix.x=123;matrix.y=-456;matrix.z=789;
    for(i=0;i<20;i++) { input[i].x=(long)random32()/16;input[i].y=(long)random32()/16;input[i].z=(long)random32()/16;input[i].normal=i; }
    calc_rotate(20,output,input,&matrix);
    for(i=0;i<20;i++) check(output[i].x==input[i].x+123 && output[i].y==input[i].y-456 && output[i].z==input[i].z+789 && output[i].normal==i,"vertex transform");
    for(i=0;i<20;i++) { input[i].x=(long)(random32()%1000000)-500000;input[i].y=(long)(random32()%1000000)-500000;input[i].z=400+i*100; }
    rt_project(20,projected,screen,input);
    for(i=0;i<20;i++) {
        long zz=input[i].z<512?512:input[i].z;
        check(screen[i].x==(long)((long long)input[i].x*projmulx/zz)+projaddx,"projection x");
        check(screen[i].y==(long)((long long)input[i].y*projmuly/zz)+projaddy,"projection y");
        check((projected[i].vf&16)==(input[i].z<512?16:0),"near flag");
        if(input[i].z>=512) check(screen[i].z==33553920L/zz,"reciprocal depth");
    }
    for(i=0;i<128;i++) {
        rmatrix a,b,old;int row,col;unsigned long sum;
        nlist normal,transformed;long xyz[3];
        for(j=0;j<9;j++) { a.m[j]=(short)random32()/2;b.m[j]=(short)random32()/2; }
        a.x=(long)random32()/64;a.y=(long)random32()/64;a.z=(long)random32()/64;
        b.x=321;b.y=-654;b.z=987;old=a;calc_applyrmatrix(&a,&b);
        for(row=0;row<3;row++) for(col=0;col<3;col++) {
            sum=(unsigned long)b.m[row*3]*old.m[col]+(unsigned long)b.m[row*3+1]*old.m[col+3]+
                (unsigned long)b.m[row*3+2]*old.m[col+6];
            check(a.m[row*3+col]==((long)sum>>14),"matrix composition");
        }
        check(a.x==dot(b.m,&old.x)+b.x && a.y==dot(b.m+3,&old.x)+b.y && a.z==dot(b.m+6,&old.x)+b.z,"matrix translation");
        xyz[0]=normal.x=(short)random32();xyz[1]=normal.y=(short)random32();xyz[2]=normal.z=(short)random32();
        calc_nrotate(1,&transformed,&normal,&b);
        check(transformed.x==(short)dot(b.m,xyz) && transformed.y==(short)dot(b.m+3,xyz) && transformed.z==(short)dot(b.m+6,xyz),"normal rotation");
    }
    puts("PASS transforms, 128 matrix/normal cases and single-pass full-width projection");
    for(i=0;i<2000;i++) {
        vlist fused[20];pvlist fp[20];rt_vertex fs[20];object box;
        int expected,actual,visible=0;
        memset(&box,0,sizeof(box));box.v0=input;box.vnum=20;box.r=&matrix;
        for(j=0;j<9;j++) matrix.m[j]=(long)random32();
        matrix.x=(long)(random32()%100000)-50000;
        matrix.y=(long)(random32()%100000)-50000;
        matrix.z=(long)(random32()%100000)-50000;
        for(j=0;j<20;j++) {
            input[j].x=(long)(random32()%20000)-10000;
            input[j].y=(long)(random32()%20000)-10000;
            input[j].z=(long)(random32()%20000)-10000;input[j].normal=j;
        }
        calc_rotate(20,output,input,&matrix);
        expected=rt_project(20,projected,screen,output);
        actual=rt_transform_project(20,fused,input,&matrix,fp,fs);
        check(expected==actual,"fused aggregate flags");
        for(j=0;j<20;j++) {
            check(fused[j].x==output[j].x && fused[j].y==output[j].y &&
                  fused[j].z==output[j].z && fused[j].normal==output[j].normal,"fused transform");
            check(fp[j].x==projected[j].x && fp[j].y==projected[j].y && fp[j].vf==projected[j].vf,"fused projection flags");
            check(fs[j].x==screen[j].x && fs[j].y==screen[j].y,"fused screen");
            if(!(fp[j].vf&16)) check(fs[j].z==screen[j].z,"fused reciprocal depth");
            if(!fp[j].vf) visible=1;
        }
        rt_bounds_init(&box);
        if(rt_bounds_outside(&box)) check(!visible,"bounds preserve visible vertices");
    }
    puts("PASS 40000 fused vertices versus separate pipeline; 2000 conservative bounds");
    for(i=0;i<263;i++) src[i]=(unsigned char)random32();
    for(n=0;n<=257;n++) {
        memset(dest,0x5a,sizeof(dest));rt_upload32(dest+3,src+1,n);
        check(!memcmp(dest+3,src+1,n) && dest[2]==0x5a && dest[3+n]==0x5a,"upload tails/guards");
    }
    puts("PASS 258 uploads, alignment, byte tails and guards");
    rt_depth_window(0,320,25,175);
    for(n=0;n<2;n++) {
    rt_triangle_kernel=n;
    for(i=0;i<sizeof(raster_cases)/sizeof(raster_cases[0]);i++) {
        unsigned long hash=2166136261UL;int x,y;
        rt_depth_begin();rt_color_begin();
        rt_raster(raster_cases[i].v,3,raster_cases[i].decal);
        for(y=0;y<200;y++) for(x=0;x<320;x++) {
            hash=(hash^rt_depth_at(x,y))*16777619UL;
            hash=(hash^rt_color_at(x,y))*16777619UL;
        }
        check(hash==raster_cases[i].hash,"complete clipped raster/row setup");
    }
    }
    rt_triangle_kernel=1;
    puts("PASS 160 complete raster images in C and assembly against portable host reference");
    {
        rt_vertex triangle[3]={{0,0,1000,32},{100,0,1000,32},{0,20,1000,32}};
        projclipy[0]=0;projclipy[1]=199;rt_depth_window(0,320,0,200);
        rt_depth_begin();rt_color_begin();rt_raster(triangle,3,0);
        check(rt_depth_at(1,1)!=0,"viewport expansion draws depth");
        projclipy[0]=25;projclipy[1]=174;rt_depth_window(0,320,25,175);
        rt_depth_begin();rt_color_begin();
        check(rt_depth_at(1,1)==0 && rt_color_at(1,1)==255,"viewport shrink clears old borders");
    }
    check_video_pages();
    puts("PASS protected-mode kernels");return 0;
}
