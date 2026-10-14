/* Editable DOS credits player. Host-built with Open Watcom, large model.
 * VGA layout and slide/split transitions follow CREDITS/MAIN.C and TWEAK.ASM.
 * Images AND ASCII captions are prepared on the host; no guest-side tools.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dos.h>
#include <conio.h>

unsigned dis_call(unsigned service);
#pragma aux dis_call = "int 0fch" parm [bx] value [ax] modify [bx cx dx si di es]

static unsigned char far *vram = (unsigned char far *)MK_FP(0xa000, 0);
static unsigned char palette[768];
static unsigned char far *caption;
static unsigned char far *picture;
static FILE *trace;

static void mode(unsigned number) {
    union REGS r;
    r.w.ax = number;
    int86(0x10, &r, &r);
}

static void graph(void) {
    mode(0x13);
    outpw(0x3c4, 0x0604);
    outpw(0x3c4, 0x0f02);
    _fmemset(vram, 0, 65535U);
    vram[65535U] = 0;
    outpw(0x3d4, 0x0014);
    outpw(0x3d4, 0xe317);
    outpw(0x3d4, 0x5013);
    outpw(0x3d4, 0x0109);
    outpw(0x3d4, 0x6418);
    outpw(0x3d4, 0x0f07);
    inp(0x3da);
    outp(0x3c0, 0x30);
    outp(0x3c0, 0x61);
}

static void split(unsigned y) {
    outpw(0x3d4, ((y & 255) << 8) | 0x18);
    outpw(0x3d4, ((((y >> 4) & 0x10) | 0x0f) << 8) | 7);
}

static void start(unsigned address) {
    outpw(0x3d4, ((address & 255) << 8) | 0x0d);
    outpw(0x3d4, (address & 0xff00) | 0x0c);
}

static void scroll(int x) {
    start(32000U + x / 4);
    inp(0x3da);
    outp(0x3c0, 0x33);
    outp(0x3c0, (x & 3) << 1);
}

static void upload(void) {
    unsigned plane, x, y, i;
    outp(0x3c8, 0);
    for (i=0; i<768; ++i) outp(0x3c9, palette[i]);
    for (plane=0; plane<4; ++plane) {
        outpw(0x3c4, (0x100 << plane) | 2);
        for (y=0; y<200; ++y)
            for (x=plane; x<320; x+=4)
                vram[y*80U+x/4] = caption[y*320U+x];
        for (y=0; y<100; ++y)
            for (x=plane; x<160; x+=4)
                vram[32000U+y*160U+100U+x/4] = picture[y*160U+x];
    }
}

static int show_card(unsigned hold) {
    long y;
    int velocity, x;
    unsigned i;
    split(400);
    start(32000U);
    dis_call(1);
    upload();
    for (y=25600L; y>0; y=y*12/13) {
        if (dis_call(2)) return 0;
        dis_call(1);
        split((unsigned)(y/128+200));
        x=320-(int)(y/80);
        scroll(x);
    }
    for (i=0; i<hold && !dis_call(2); ++i) dis_call(1);
    for (y=0,velocity=0; y<25600L; y+=velocity,velocity+=15) {
        if (dis_call(2)) return 0;
        dis_call(1);
        split((unsigned)(y/128+200));
        x=320+(int)(y/80);
        scroll(x);
    }
    return 1;
}

static int fail(const char *message) {
    if (trace) { fprintf(trace,"ERROR: %s\n",message); fclose(trace); }
    mode(3);
    printf("RT1715 credits: %s\n",message);
    return 1;
}

int main(void) {
    FILE *index, *card;
    unsigned count, number, hold;
    unsigned far *vector = (unsigned far *)MK_FP(0, 0xfc*4);
    unsigned far *signature;
    char name[13], magic[4];
    if (vector[0] < 4) return 1;
    signature = (unsigned far *)MK_FP(vector[1],vector[0]-4);
    if (signature[0]!=0x0fc0 || signature[1]!=0x0fc0) {
        puts("Run RT1715.EXE, not CRED.EXE directly.");
        return 1;
    }
    dis_call(0);
    trace=fopen("CRED.LOG","wt");
    index=fopen("CRED.IDX","rt");
    if (!index) return fail("cannot open CRED.IDX");
    if (fscanf(index,"RT1715 %u",&count)!=1 || count<1 || count>99)
        return fail("invalid credit index");
    caption=(unsigned char far *)malloc(64000U);
    picture=(unsigned char far *)malloc(16000U);
    if (!caption || !picture) return fail("not enough memory for credit buffers");
    graph();
    for (number=0; number<count && !dis_call(2); ++number) {
        if (fscanf(index,"%12s %u",name,&hold)!=2 || hold<1 || hold>4200)
            return fail("invalid credit entry");
        card=fopen(name,"rb");
        if (!card) return fail("cannot open credit card");
        if (fread(magic,1,4,card)!=4 || memcmp(magic,"CRD1",4) ||
            fread(palette,1,768,card)!=768 ||
            fread(caption,1,64000U,card)!=64000U ||
            fread(picture,1,16000U,card)!=16000U || fgetc(card)!=EOF)
            return fail("invalid or truncated credit card");
        fclose(card);
        if (trace) { fprintf(trace,"CARD %u %s\n",number+1,name); fflush(trace); }
        if (!show_card(hold)) break;
    }
    fclose(index);
    free(caption);
    free(picture);
    if (trace) {
        fprintf(trace,number==count ? "COMPLETE\n" : "ABORTED\n");
        fclose(trace);
    }
    return 0;
}
