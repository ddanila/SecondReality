/* Opaque ink over the translucent key. Cache before the secondary object
 * reuses the projection buffer; reject back-facing/near-clipped legends. */
static unsigned char far rt_legend_back[8192];
static int rt_legend_saved,rt_bx,rt_by,rt_bw,rt_bh;
static void rt_legend_restore(void) {
    int y;
    if(rt_legend_saved)for(y=0;y<rt_bh;y++)
        _fmemcpy(vram+(unsigned)(rt_by+y)*320+rt_bx,rt_legend_back+y*rt_bw,rt_bw);
    rt_legend_saved=0;
}
static int rt_legend_xy[18][4][2],rt_legend_ready;
static void rt_legend_capture(int *points)
{
    int face,i,index;long area;
    rt_legend_ready=0;
    for(face=0;face<18;face++)for(i=0;i<4;i++) {
        if(face<16) {
            int v=i>=2?32:16+(face+i)%16;
            index=2+v*6;
        } else index=2+(33+(face-16)*4+i)*6;
        if(points[index+2]&16)return;
        rt_legend_xy[face][i][0]=points[index];
        rt_legend_xy[face][i][1]=points[index+1];
    }
    area=(long)(rt_legend_xy[16][0][0]-rt_legend_xy[16][1][0])*
               (rt_legend_xy[16][0][1]-rt_legend_xy[16][2][1])-
         (long)(rt_legend_xy[16][0][1]-rt_legend_xy[16][1][1])*
               (rt_legend_xy[16][0][0]-rt_legend_xy[16][2][0]);
    rt_legend_ready=area>0;
}
static void rt_legend_draw(void)
{
    int face,i,j,y,ymin,ymax,xleft,xright,x,y0,y1;
    if(!rt_legend_ready)return;
    rt_bx=320;rt_by=200;rt_bw=0;rt_bh=0;
    for(face=0;face<18;face++)for(i=0;i<4;i++) {
        x=rt_legend_xy[face][i][0];y=rt_legend_xy[face][i][1];
        if(x<0||x>319||y<0||y>199)return;
        if(x<rt_bx)rt_bx=x;if(x>rt_bw)rt_bw=x;
        if(y<rt_by)rt_by=y;if(y>rt_bh)rt_bh=y;
    }
    rt_bw=rt_bw-rt_bx+1;rt_bh=rt_bh-rt_by+1;
    if((long)rt_bw*rt_bh>8192)return;
    for(y=0;y<rt_bh;y++)_fmemcpy(rt_legend_back+y*rt_bw,vram+(unsigned)(rt_by+y)*320+rt_bx,rt_bw);
    rt_legend_saved=1;
    outp(0x3c8,255);outp(0x3c9,55);outp(0x3c9,53);outp(0x3c9,46);
    for(face=0;face<18;face++) {
        ymin=200;ymax=-1;
        for(i=0;i<4;i++) {
            y=rt_legend_xy[face][i][1];
            if(y<ymin)ymin=y;if(y>ymax)ymax=y;
        }
        if(ymin<0)ymin=0;if(ymax>200)ymax=200;
        for(y=ymin;y<ymax;y++) {
            xleft=320;xright=-1;
            for(i=0;i<4;i++) {
                j=(i+1)&3;y0=rt_legend_xy[face][i][1];y1=rt_legend_xy[face][j][1];
                if(!((y0<=y&&y1>y)||(y1<=y&&y0>y)))continue;
                x=rt_legend_xy[face][i][0]+(long)(y-y0)*
                  (rt_legend_xy[face][j][0]-rt_legend_xy[face][i][0])/(y1-y0);
                if(x<xleft)xleft=x;if(x>xright)xright=x;
            }
            if(xleft<0)xleft=0;if(xright>319)xright=319;
            if(xright>=xleft)memset(vram+(unsigned)y*320+xleft,face<16?255:0,xright-xleft+1);
        }
    }
}
