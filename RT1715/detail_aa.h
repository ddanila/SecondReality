/* Sixteen-sample coverage for small surface markings, with Q4 projection.
 * Deferred until opaque depth is complete: no draw-order-dependent blending.
 * Only touched pixels are reset/composited; ordinary geometry keeps ASM spans. */
#if defined(RT_HOST_TEST) || defined(RT_PM)
static unsigned short *detail_z,*detail_touched,*detail_mask;
static unsigned char *detail_color,*detail_alpha;
static unsigned detail_opacity=255;
void rt_detail_opacity(unsigned opacity) { detail_opacity=opacity>255?255:opacity; }
static unsigned detail_count;
static const unsigned char *detail_palette,*detail_lookup;
int rt_detail_enabled(void) {
#ifdef RT_PM
    return detail_lookup && rt_ram_color;
#else
    return detail_lookup!=0;
#endif
}
void rt_detail_init(const unsigned char *palette,const unsigned char *lookup) {
    detail_palette=palette;detail_lookup=lookup;
    if(lookup && !detail_z) {
        detail_z=calloc(1024000,sizeof(*detail_z));detail_color=malloc(1024000);detail_alpha=malloc(1024000);
        detail_mask=calloc(64000,sizeof(*detail_mask));detail_touched=malloc(64000*sizeof(*detail_touched));
        if(!detail_z || !detail_color || !detail_alpha || !detail_mask || !detail_touched) exit(3);
    }
}
static void detail_begin(void) {
    unsigned i,j,p;
    for(i=0;i<detail_count;i++) {
        p=detail_touched[i];detail_mask[p]=0;
        for(j=0;j<16;j++) detail_z[p*16+j]=0;
    }
    detail_count=0;
}
static void detail_end(void) {
    free(detail_alpha);detail_alpha=0;free(detail_z);free(detail_color);free(detail_mask);free(detail_touched);
    detail_z=detail_touched=0;detail_color=0;detail_mask=0;
    detail_palette=detail_lookup=0;detail_count=0;
}
static long detail_edge(const rt_vertex *a,const rt_vertex *b,long x,long y) {
    return (b->x-a->x)*(y-a->y)-(b->y-a->y)*(x-a->x);
}
static int detail_inside(long e,const rt_vertex *a,const rt_vertex *b) {
    return e>0 || (e==0 && (b->y<a->y || (b->y==a->y && b->x>a->x)));
}
static void detail_triangle(rt_vertex a,rt_vertex b,rt_vertex c) {
    rt_vertex swap;long area,x0,x1,y0,y1,x,y,e0,e1,e2,z,dx0,dx1,dx2,dy0,dy1,dy2,bias,gx,gy;
    unsigned p,k,s,color=(unsigned)a.c;int sample,have_depth;
    area=detail_edge(&a,&b,c.x,c.y);if(!area) return;
    if(area<0) { swap=b;b=c;c=swap;area=-area; }
    /* Opaque vertices are rounded to whole pixels, while ink uses Q4.
     * Bound that one-pixel depth-plane displacement in both screen axes. */
    gx=rt_muldiv(b.z-a.z,(a.y-c.y)*16,area)+rt_muldiv(c.z-a.z,(b.y-a.y)*16,area);
    gy=rt_muldiv(b.z-a.z,(c.x-a.x)*16,area)+rt_muldiv(c.z-a.z,(a.x-b.x)*16,area);
    bias=labs(gx)+labs(gy)+2;
    x0=a.x;if(b.x<x0)x0=b.x;if(c.x<x0)x0=c.x;
    x1=a.x;if(b.x>x1)x1=b.x;if(c.x>x1)x1=c.x;
    y0=a.y;if(b.y<y0)y0=b.y;if(c.y<y0)y0=c.y;
    y1=a.y;if(b.y>y1)y1=b.y;if(c.y>y1)y1=c.y;
    x0/=16;x1=(x1+15)/16;y0/=16;y1=(y1+15)/16;
    /* Increment edge equations across the 4x4 grid: no per-sample multiplies. */
    dx0=(b.y-c.y)*4;dx1=(c.y-a.y)*4;dx2=(a.y-b.y)*4;
    dy0=(c.x-b.x)*4-dx0*4;dy1=(a.x-c.x)*4-dx1*4;dy2=(b.x-a.x)*4-dx2*4;
    for(y=y0;y<y1;y++) for(x=x0;x<x1;x++) {
      have_depth=0;
      e0=detail_edge(&b,&c,x*16+2,y*16+2);
      e1=detail_edge(&c,&a,x*16+2,y*16+2);
      e2=detail_edge(&a,&b,x*16+2,y*16+2);
      for(sample=0;sample<16;sample++,e0+=dx0,e1+=dx1,e2+=dx2) {
        if(sample && !(sample&3)) { e0+=dy0;e1+=dy1;e2+=dy2; }
        if(!detail_inside(e0,&b,&c) || !detail_inside(e1,&c,&a) || !detail_inside(e2,&a,&b)) continue;
        /* Compare decal and opaque depth at the same pixel centre. Sample
         * positions control coverage, not a spurious surface-depth slope. */
        if(!have_depth) {
            z=a.z+rt_muldiv(b.z-a.z,detail_edge(&c,&a,x*16+8,y*16+8),area)
                 +rt_muldiv(c.z-a.z,detail_edge(&a,&b,x*16+8,y*16+8),area)+bias;
            have_depth=1;
        }
        if(z<1)continue;if(z>65535)z=65535;
        p=(unsigned)(y*320+x);k=p*16+sample;
        if(z<detail_z[k])continue;
        if(!detail_mask[p])detail_touched[detail_count++]=(unsigned short)p;
        detail_mask[p]|=1<<sample;detail_z[k]=(unsigned short)z;detail_color[k]=(unsigned char)color;detail_alpha[k]=(unsigned char)detail_opacity;
      }
    }
}
void rt_detail_raster(rt_vertex *v,int count) {
    rt_vertex a[16],b[16];int n=count,i;
    if(!detail_opacity || !rt_detail_enabled() || n<3 || n>8)return;
    memcpy(a,v,n*sizeof(*v));
    n=clip(a,b,n,0,clip_left*16,0);if(n<3)return;
    n=clip(b,a,n,0,clip_right*16,1);if(n<3)return;
    n=clip(a,b,n,1,clip_top*16,0);if(n<3)return;
    n=clip(b,a,n,1,clip_bottom*16,1);if(n<3)return;
    for(i=1;i<n-1;i++)detail_triangle(a[0],a[i],a[i+1]);
}
static void detail_flush(void) {
    unsigned i,j,p,k,bg,color,r,g,b,visible,first,same,alpha;unsigned short *depth=depth_memory();
    if(!rt_detail_enabled())return;
    for(i=0;i<detail_count;i++) {
        p=detail_touched[i];
#ifdef RT_HOST_TEST
        bg=test_color[p];
#else
        k=(p%320&3)*16000+(p/320)*80+(p%320>>2);bg=rt_color[k];
#endif
        r=g=b=visible=0;first=256;same=1;
        for(j=0;j<16;j++) {
            color=bg;alpha=256;
            if((detail_mask[p]&(1<<j)) && detail_z[p*16+j]>=depth[p]) { color=detail_color[p*16+j];alpha=detail_alpha[p*16+j];if(alpha==255)alpha=256;visible++; }
            if(first==256)first=color;else if(first!=color)same=0;
            if(alpha!=256 && color!=bg)same=0;
            r+=detail_palette[color*3]*alpha+detail_palette[bg*3]*(256-alpha);
            g+=detail_palette[color*3+1]*alpha+detail_palette[bg*3+1]*(256-alpha);
            b+=detail_palette[color*3+2]*alpha+detail_palette[bg*3+2]*(256-alpha);
        }
        if(!visible)continue;
        color=same?first:detail_lookup[((r>>13)<<10)|((g>>13)<<5)|(b>>13)];
#ifdef RT_HOST_TEST
        test_color[p]=(unsigned char)color;
#else
        rt_color[k]=(unsigned char)color;
#endif
    }
}
#else
void rt_detail_opacity(unsigned opacity) { }
int rt_detail_enabled(void) { return 0; }
void rt_detail_init(const unsigned char *p,const unsigned char *l) { }
void rt_detail_raster(rt_vertex *v,int n) { }
static void detail_begin(void) { }
static void detail_end(void) { }
static void detail_flush(void) { }
#endif
