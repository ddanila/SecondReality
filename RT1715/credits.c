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
static FILE *active_card;
static unsigned reveal_count,reveal_cs,reveal_frame,total_cards;
#define CARD_PIXELS 80772L
static int read_reveal(unsigned frame) {
    if(frame==reveal_frame) return 1;
    if(fseek(active_card,CARD_PIXELS+4L+(long)frame*16000L,SEEK_SET) ||
       fread(picture,1,16000U,active_card)!=16000U) return 0;
    reveal_frame=frame;return 1;
}
unsigned music_position(void);
#pragma aux music_position = "mov bx,6" "int 0fch" "shl cx,6" "or bx,cx" "mov ax,bx" value [ax] modify [bx cx dx]

/* Optional Robotron schedule: exact tracker cues, smooth retrace interpolation.
 * Generic editable projects retain the original fixed-frame transitions. */
static unsigned clock_rows[16][64];
static unsigned cues[99][4],scheduled=0,last_pos=65535,last_tick;
unsigned long clock_snapshot(void);
#pragma aux clock_snapshot = "mov bx,11" "int 0fch" value [dx ax] modify [bx cx si di es]
static unsigned credit_time(void) {
    unsigned long snapshot=clock_snapshot();unsigned pos=(unsigned)snapshot,tick=(unsigned)(snapshot>>16),order=pos>>6;
    if(pos!=last_pos) { last_pos=pos;last_tick=tick; }
    if(order<28) return 0;if(order>43) return 65535;
    return clock_rows[order-28][pos&63]+(unsigned short)(tick-last_tick)*100U/70U;
}
static void dim_palette(unsigned scale) {
    unsigned i;outp(0x3c8,0);
    for(i=0;i<768;i++) outp(0x3c9,(unsigned)palette[i]*scale/64);
}
static unsigned credit_cue=0;
static void log_position(const char *event) {
    unsigned pos=music_position();
    if(trace) { fprintf(trace,"%s order=%u row=%u\n",event,pos>>6,pos&63); fflush(trace); }
}

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

static void upload_picture(void) {
    unsigned plane,x,y;
    for(plane=0;plane<4;plane++) {
        outpw(0x3c4,(0x100<<plane)|2);
        for(y=0;y<100;y++) for(x=plane;x<160;x+=4)
            vram[32000U+y*160U+100U+x/4]=picture[y*160U+x];
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

static int show_scheduled(unsigned number) {
    unsigned now,t,scale=65535,next_scale;long y;
    unsigned *cue=cues[number];
    /* Prepare while blank; keep file and palette work ahead of the entry cue. */
    if(reveal_count && !read_reveal(0)) return 0;
    split(400);scroll(0);upload();dim_palette(0);
    while(music_position()<credit_cue && !dis_call(2)) dis_call(1);
    while(credit_time()<cue[0] && !dis_call(2)) dis_call(1);
    if(number==0) log_position("START");
    log_position("ENTRY");
    while((now=credit_time())<cue[3]) {
        if(dis_call(2)) return 0;
        if(now<cue[1]) {
            t=(unsigned)((long)(now-cue[0])*256/(cue[1]-cue[0]));
            y=256-(long)t;y=y*y/256*y/256;y=25600L*y/256;
            split((unsigned)(y/128+200));scroll(320-(int)(y/80));
            next_scale=t<64?t:64;
        } else if(now<cue[2]) {
            if(reveal_count) {
                unsigned frame=(unsigned)((long)(now-cue[1])*(reveal_count-1)/reveal_cs);
                if(frame>=reveal_count) frame=reveal_count-1;
                if(frame!=reveal_frame) {
                    if(!read_reveal(frame)) return 0;
                    upload_picture();
                }
            }
            split(200);scroll(320);next_scale=64;
        } else {
            t=(unsigned)((long)(now-cue[2])*256/(cue[3]-cue[2]));
            y=25600L*t*t/65536L;
            if(number+1==total_cards) { split(200);scroll(320); }
            else { split((unsigned)(y/128+200));scroll(320+(int)(y/80)); }
            next_scale=64-t/4;
        }
        if(next_scale!=scale) { dim_palette(next_scale);scale=next_scale; }
        dis_call(1);
    }
    dim_palette(0);split(400);scroll(0);return 1;
}

static int fail(const char *message) {
    if (trace) { fprintf(trace,"ERROR: %s\n",message); fclose(trace); }
    mode(3);
    printf("RT1715 credits: %s\n",message);
    return 1;
}

int main(void) {
    FILE *index, *card, *sync, *schedule, *clock_file;
    unsigned count, number, hold, cue_order, cue_row;
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
    total_cards=count;
    caption=(unsigned char far *)malloc(64000U);
    picture=(unsigned char far *)malloc(16000U);
    if (!caption || !picture) return fail("not enough memory for credit buffers");
    sync=fopen("CRED.SYN","rt");
    if(sync) {
        if(fscanf(sync,"%u %u",&cue_order,&cue_row)!=2 || cue_order>79 || cue_row>63)
            return fail("invalid music cue");
        credit_cue=cue_order*64+cue_row;
        fclose(sync);
    }
    schedule=fopen("CRED.CUE","rt");
    if(schedule) {
        unsigned declared,i;
        if(fscanf(schedule,"%u",&declared)!=1 || declared!=count) return fail("invalid cue count");
        for(i=0;i<count;i++) {
            if(fscanf(schedule,"%u %u %u %u",&cues[i][0],&cues[i][1],&cues[i][2],&cues[i][3])!=4 ||
               !(cues[i][0]<cues[i][1] && cues[i][1]<cues[i][2] && cues[i][2]<cues[i][3]) ||
               (i && cues[i][0]<cues[i-1][3])) return fail("invalid card cues");
        }
        fclose(schedule);clock_file=fopen("CRED.TIM","rb");
        if(!clock_file || fread(clock_rows,1,sizeof(clock_rows),clock_file)!=sizeof(clock_rows) || fgetc(clock_file)!=EOF)
            return fail("invalid tracker clock");
        fclose(clock_file);scheduled=1;
    }
    for (number=0; number<count && !dis_call(2); ++number) {
        if (fscanf(index,"%12s %u",name,&hold)!=2 || hold<1 || hold>4200)
            return fail("invalid credit entry");
        card=fopen(name,"rb");
        if (!card) return fail("cannot open credit card");
        if (fread(magic,1,4,card)!=4 || (memcmp(magic,"CRD1",4) && memcmp(magic,"CRD2",4)) ||
            fread(palette,1,768,card)!=768 ||
            fread(caption,1,64000U,card)!=64000U ||
            fread(picture,1,16000U,card)!=16000U)
            return fail("invalid or truncated credit card");
        reveal_count=0;reveal_frame=65535;active_card=card;
        if(!memcmp(magic,"CRD2",4)) {
            long expected;
            if(fread(&reveal_count,2,1,card)!=1 || fread(&reveal_cs,2,1,card)!=1 ||
               reveal_count<2 || reveal_count>16 || reveal_cs<20 || reveal_cs>100)
                return fail("invalid reveal header");
            expected=CARD_PIXELS+4L+(long)reveal_count*16000L;
            if(fseek(card,0,SEEK_END) || ftell(card)!=expected)
                return fail("truncated reveal frames");
        } else if(fgetc(card)!=EOF) return fail("unexpected card payload");
        if(number==0) {
            log_position("READY");
            if(!scheduled) {
                while(credit_cue && music_position()<credit_cue && !dis_call(2)) dis_call(1);
                log_position("START");
            }
            graph();
        }
        if (trace) { fprintf(trace,"CARD %u %s\n",number+1,name); fflush(trace); }
        if (!(scheduled?show_scheduled(number):show_card(hold))) { fclose(card);break; }
        fclose(card);
    }
    log_position("END");
    fclose(index);
    free(caption);
    free(picture);
    if (trace) {
        fprintf(trace,number==count ? "COMPLETE\n" : "ABORTED\n");
        fclose(trace);
    }
    return 0;
}
