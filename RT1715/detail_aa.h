/* Four-sample coverage for small surface markings, with Q4 projection.
 * Deferred until opaque depth is complete: no draw-order-dependent blending.
 * Only touched pixels are reset/composited; ordinary geometry keeps ASM spans. */
#if defined(RT_HOST_TEST) || defined(RT_PM)
static unsigned short *detail_z,*detail_touched;
static unsigned char *detail_color,*detail_mask;
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
        detail_z=calloc(256000,sizeof(*detail_z));detail_color=malloc(256000);
        detail_mask=calloc(64000,1);detail_touched=malloc(64000*sizeof(*detail_touched));
        if(!detail_z || !detail_color || !detail_mask || !detail_touched) exit(3);
    }
}
static void detail_begin(void) {
    unsigned i,j,p;
    for(i=0;i<detail_count;i++) {
        p=detail_touched[i];detail_mask[p]=0;
        for(j=0;j<4;j++) detail_z[p*4+j]=0;
    }
    detail_count=0;
}
static void detail_end(void) {
    free(detail_z);free(detail_color);free(detail_mask);free(detail_touched);
    detail_z=detail_touched=0;detail_color=detail_mask=0;
    detail_palette=detail_lookup=0;detail_count=0;
}
static long detail_edge(const rt_vertex *a,const rt_vertex *b,long x,long y) {
    return (b->x-a->x)*(y-a->y)-(b->y-a->y)*(x-a->x);
}
static int detail_inside(long e,const rt_vertex *a,const rt_vertex *b) {
    return e>0 || (e==0 && (b->y<a->y || (b->y==a->y && b->x>a->x)));
}
static void detail_triangle(rt_vertex a,rt_vertex b,rt_vertex c) {
    rt_vertex swap;long area,x0,x1,y0,y1,x,y,sx,sy,e0,e1,e2,z;
    unsigned p,k,s,color=(unsigned)a.c;int sample;
    area=detail_edge(&a,&b,c.x,c.y);if(!area) return;
    if(area<0) { swap=b;b=c;c=swap;area=-area; }
    x0=a.x;if(b.x<x0)x0=b.x;if(c.x<x0)x0=c.x;
    x1=a.x;if(b.x>x1)x1=b.x;if(c.x>x1)x1=c.x;
    y0=a.y;if(b.y<y0)y0=b.y;if(c.y<y0)y0=c.y;
    y1=a.y;if(b.y>y1)y1=b.y;if(c.y>y1)y1=c.y;
    x0/=16;x1=(x1+15)/16;y0/=16;y1=(y1+15)/16;
    for(y=y0;y<y1;y++) for(x=x0;x<x1;x++) for(sample=0;sample<4;sample++) {
        sx=x*16+4+(sample&1)*8;sy=y*16+4+(sample>>1)*8;
        e0=detail_edge(&b,&c,sx,sy);e1=detail_edge(&c,&a,sx,sy);e2=detail_edge(&a,&b,sx,sy);
        if(!detail_inside(e0,&b,&c) || !detail_inside(e1,&c,&a) || !detail_inside(e2,&a,&b)) continue;
        z=a.z+rt_muldiv(b.z-a.z,e1,area)+rt_muldiv(c.z-a.z,e2,area)+1;
        if(z<1)continue;if(z>65535)z=65535;
        p=(unsigned)(y*320+x);k=p*4+sample;
        if(z<detail_z[k])continue;
        if(!detail_mask[p])detail_touched[detail_count++]=(unsigned short)p;
        detail_mask[p]|=1<<sample;detail_z[k]=(unsigned short)z;detail_color[k]=(unsigned char)color;
    }
}
void rt_detail_raster(rt_vertex *v,int count) {
    rt_vertex a[16],b[16];int n=count,i;
    if(!rt_detail_enabled() || n<3 || n>8)return;
    memcpy(a,v,n*sizeof(*v));
    n=clip(a,b,n,0,clip_left*16,0);if(n<3)return;
    n=clip(b,a,n,0,clip_right*16,1);if(n<3)return;
    n=clip(a,b,n,1,clip_top*16,0);if(n<3)return;
    n=clip(b,a,n,1,clip_bottom*16,1);if(n<3)return;
    for(i=1;i<n-1;i++)detail_triangle(a[0],a[i],a[i+1]);
}
static void detail_flush(void) {
    unsigned i,j,p,k,bg,color,r,g,b,visible,first,same;unsigned short *depth=depth_memory();
    if(!rt_detail_enabled())return;
    for(i=0;i<detail_count;i++) {
        p=detail_touched[i];
#ifdef RT_HOST_TEST
        bg=test_color[p];
#else
        k=(p%320&3)*16000+(p/320)*80+(p%320>>2);bg=rt_color[k];
#endif
        r=g=b=visible=0;first=256;same=1;
        for(j=0;j<4;j++) {
            color=bg;
            if((detail_mask[p]&(1<<j)) && detail_z[p*4+j]>=depth[p]) { color=detail_color[p*4+j];visible++; }
            if(first==256)first=color;else if(first!=color)same=0;
            r+=detail_palette[color*3];g+=detail_palette[color*3+1];b+=detail_palette[color*3+2];
        }
        if(!visible)continue;
        color=same?first:detail_lookup[((r>>3)<<10)|((g>>3)<<5)|(b>>3)];
#ifdef RT_HOST_TEST
        test_color[p]=(unsigned char)color;
#else
        rt_color[k]=(unsigned char)color;
#endif
    }
}
#else
int rt_detail_enabled(void) { return 0; }
void rt_detail_init(const unsigned char *p,const unsigned char *l) { }
void rt_detail_raster(rt_vertex *v,int n) { }
static void detail_begin(void) { }
static void detail_end(void) { }
static void detail_flush(void) { }
#endif
