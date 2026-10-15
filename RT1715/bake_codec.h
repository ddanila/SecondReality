/* Shared DOS/host decoder; no platform dependencies. */
#include <string.h>
static unsigned rt_unpack_word(const unsigned char *p){return p[0]|((unsigned)p[1]<<8);}
/* LZ4 block format, with bounds checked before every length/read/copy. */
int rt_unpack_block(const unsigned char *src,unsigned size,unsigned char *dst,unsigned length) {
    const unsigned char *end=src+size;unsigned char *out=dst,*limit=dst+length;
    unsigned token,n,value,offset;
    while(src<end) {
        token=*src++;n=token>>4;
        if(n==15)do {if(src==end)return 0;value=*src++;if(value>length || n>length-value)return 0;n+=value;}while(value==255);
        if(n>(unsigned)(end-src) || n>(unsigned)(limit-out))return 0;
        memcpy(out,src,n);out+=n;src+=n;if(src==end)return out==limit;
        if(end-src<2)return 0;offset=rt_unpack_word(src);src+=2;if(!offset || offset>(unsigned)(out-dst))return 0;
        n=token&15;
        if(n==15)do {if(src==end)return 0;value=*src++;if(value>length || n>length-value)return 0;n+=value;}while(value==255);
        if(n>length-4)return 0;n+=4;if(n>(unsigned)(limit-out))return 0;
        /* Nonoverlapping matches can use the compiler's bulk copy. */
        if(offset>=n){memcpy(out,out-offset,n);out+=n;}
        else while(n--){*out=out[-(int)offset];out++;}
    }
    return out==limit;
}
