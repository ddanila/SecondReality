#!/usr/bin/env python3
"""Render one credit, its exact quantized reveal, and reading-time report on host."""
import argparse,json,struct
from pathlib import Path
from PIL import Image
from presentation import load,DEFAULT
from credit_scene import load_scene
from credit_views import render_cards
from prepare import make_card
from music import write_credit_schedule

HERE=Path(__file__).resolve().parent


def decode(path):
    data=Path(path).read_bytes()
    if len(data)<80772 or data[:4] not in (b'CRD1',b'CRD2'):raise ValueError('Invalid card')
    palette=[v*255//63 for v in data[4:772]]
    def im(raw,size):
        out=Image.frombytes('P',size,raw);out.putpalette(palette);return out.convert('RGB')
    caption=im(data[772:64772],(320,200));picture=im(data[64772:80772],(160,100))
    frames=[];duration=0
    if data[:4]==b'CRD2':
        if len(data)<80776:raise ValueError('Truncated card')
        count,duration=struct.unpack_from('<HH',data,80772)
        if not 2<=count<=16 or not 20<=duration<=100 or len(data)!=80776+count*16000:raise ValueError('Invalid reveal')
        frames=[im(data[80776+i*16000:80776+(i+1)*16000],(160,100)) for i in range(count)]
    elif len(data)!=80772:raise ValueError('Unexpected static payload')
    return caption,picture,frames,duration


def composition(caption,picture):
    out=Image.new('RGB',(640,480),'black')
    out.paste(picture.resize((320,240),Image.Resampling.NEAREST),(160,0))
    out.paste(caption.resize((640,240),Image.Resampling.NEAREST),(0,240))
    return out


def export_preview(card_path,cue,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    caption,picture,frames,duration=decode(card_path)
    motion=duration if frames else 0
    reading=cue['exit_start_cs']-cue['enter_end_cs']-motion
    if reading<250:raise ValueError('Less than 2.5 seconds remain still for reading')
    still=composition(caption,frames[-1] if frames else picture);still.save(output/'still.png')
    still.resize((320,240),Image.Resampling.NEAREST).save(output/'actual-size.png')
    shots=[composition(caption,p) for p in frames] if frames else [still]
    durations=([round(duration*10/(len(frames)-1))]*(len(frames)-1)+[reading*10]) if frames else [reading*10]
    # APNG retains the exact quantized colors; the hold is included once per loop.
    shots[0].save(output/'reveal.png',save_all=True,append_images=shots[1:],duration=durations,loop=0,disposal=0,blend=0)
    report={'entry_cue':[cue['order'],cue['row']],'entry_seconds':(cue['enter_end_cs']-cue['start_cs'])/100,
            'motion_seconds':motion/100,'static_reading_seconds':reading/100,
            'exit_seconds':(cue['end_cs']-cue['exit_start_cs'])/100,
            'slot_seconds':(cue['end_cs']-cue['start_cs'])/100,'picture_size':[160,100],
            'preview_size':[640,480],'small_preview_size':[320,240],
            'preview_scope':'Quantized picture motion and stable caption; DOS entry/exit scroll is not simulated.'}
    (output/'timing.json').write_text(json.dumps(report,indent=2)+'\n');return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('card',help='Image ID or 1-based card number')
    p.add_argument('--manifest',type=Path,default=DEFAULT);p.add_argument('--source',type=Path)
    p.add_argument('--output',type=Path);p.add_argument('--openscad',default='openscad');args=p.parse_args()
    config,root,files=load(args.manifest,args.source);cards=json.loads(files['credits'].read_text())
    matches=[(i,c) for i,c in enumerate(cards) if c['image']==args.card or str(i+1)==args.card]
    if len(matches)!=1:p.error('Choose an existing image ID or card number')
    index,card=matches[0];out=(args.output or HERE/'build/credit-previews'/card['image']).resolve();out.mkdir(parents=True,exist_ok=True)
    geometry=out/'geometry';geometry.mkdir(exist_ok=True)
    records,mesh,chips,keys=load_scene(root,geometry,args.openscad)
    item=render_cards(files['credits'],geometry,records,mesh,chips,keys,args.openscad,only=card['image'])[0]
    make_card(item['image'],item['lines'],out/'CARD.CRD',out/'draft.png',item.get('reveal_frames',[]),item.get('reveal_cs',80))
    write_credit_schedule(HERE.parent/'MAIN/MUSIC0.S3M',out,config['transition'],len(cards))
    cue=json.loads((out/'credit-cues.json').read_text())[index]
    report=export_preview(out/'CARD.CRD',cue,out)
    print(f"{card['image']}: {report['motion_seconds']:.2f}s motion, {report['static_reading_seconds']:.2f}s still reading; {out}")

if __name__=='__main__':main()
