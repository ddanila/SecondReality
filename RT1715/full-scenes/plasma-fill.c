/* Clipped convex scan conversion for the original planar span writer.
 * The released cube stayed inside its 640-pixel virtual framebuffer. Thin
 * package pins can straddle an edge; never index its unrolled jump table with
 * an unclipped span. Texture coordinates retain the original affine mapping.
 */
struct clip_point { long x,y,u,v; };
static struct clip_point clip_a[12],clip_b[12];
static int clip_edge(struct clip_point *in, struct clip_point *out,int n,
                     int axis,long bound,int keep_greater)
{
    int i,m=0,inside,previous_inside;
    struct clip_point previous=in[n-1],current,hit;
    long a,b,t;
    a=axis?previous.y:previous.x;
    previous_inside=keep_greater?a>=bound:a<=bound;
    for(i=0;i<n;i++) {
        current=in[i];b=axis?current.y:current.x;
        inside=keep_greater?b>=bound:b<=bound;
        if(inside!=previous_inside) {
            t=(bound-a)*256L/(b-a);
            hit.x=previous.x+(current.x-previous.x)*t/256;
            hit.y=previous.y+(current.y-previous.y)*t/256;
            hit.u=previous.u+(current.u-previous.u)*t/256;
            hit.v=previous.v+(current.v-previous.v)*t/256;
            if(axis)hit.y=bound;else hit.x=bound;
            out[m++]=hit;
        }
        if(inside)out[m++]=current;
        previous=current;a=b;previous_inside=inside;
    }
    return m;
}
void do_poly(int x1,int y1,int x2,int y2,int x3,int y3,int x4,int y4,int color,int dd)
{
    int n=4,i,j,y,ymin=134,ymax=0,found;
    long fy,t,x,u,v,lx,rx,lu,ru,lv,rv;
    int xs[4],ys[4];
    xs[0]=x1;xs[1]=x2;xs[2]=x3;xs[3]=x4;
    ys[0]=y1;ys[1]=y2;ys[2]=y3;ys[3]=y4;
    for(i=0;i<4;i++) {
        clip_a[i].x=(long)xs[i]*256;clip_a[i].y=(long)ys[i]*256;
        clip_a[i].u=(i==1||i==2)?190L*256:64L*256;
        clip_a[i].v=i>=2?60L*256:4L*256;
    }
    n=clip_edge(clip_a,clip_b,n,0,0,1);if(n<3)return;
    n=clip_edge(clip_b,clip_a,n,0,639L*256,0);if(n<3)return;
    n=clip_edge(clip_a,clip_b,n,1,0,1);if(n<3)return;
    n=clip_edge(clip_b,clip_a,n,1,134L*256,0);if(n<3)return;
    for(i=0;i<n;i++) {
        y=(int)(clip_a[i].y/256);
        if(y<ymin)ymin=y;if(y>ymax)ymax=y;
    }
    from=MK_FP(kuvataus[color],0);
    dseg=disttaus[color]+((dd+1)&63)*16;
    ax1=ax2=tax1=tax2=tay1=tay2=0;
    for(y=ymin;y<ymax;y++) {
        fy=(long)y*256+128;found=0;lx=0x7fffffffL;rx=-0x7fffffffL;
        for(i=0;i<n;i++) {
            j=(i+1)%n;
            if(!((clip_a[i].y<=fy&&clip_a[j].y>fy)||
                 (clip_a[j].y<=fy&&clip_a[i].y>fy)))continue;
            t=(fy-clip_a[i].y)*256/(clip_a[j].y-clip_a[i].y);
            x=clip_a[i].x+(clip_a[j].x-clip_a[i].x)*t/256;
            u=clip_a[i].u+(clip_a[j].u-clip_a[i].u)*t/256;
            v=clip_a[i].v+(clip_a[j].v-clip_a[i].v)*t/256;
            if(x<lx){lx=x;lu=u;lv=v;}if(x>rx){rx=x;ru=u;rv=v;}found++;
        }
        if(found<2||rx<=lx)continue;
        yy=y;xx2=lx*256;xx1=rx*256;
        txx2=lu*256;txy2=lv*256;txx1=ru*256;txy1=rv*256;
        to=vmem[y];ctau=&clrtau[clrptr][y][0];do_block(1);
    }
}
