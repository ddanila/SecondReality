#!/usr/bin/env python3
"""Build a labelled review reel and contact sheet from verified DOS playback."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
from PIL import Image,ImageDraw,ImageFont

HERE=Path(__file__).resolve().parent
SHOTS=[('KEYBOARD',8,4),('KEYPAD / TURN',17,3),('DRIVE FRONTS',30,4),
       ('MONITOR SEAM',43,3),('CRT GLASS',46,2),('FULL REVEAL',50,3),
       ('DRONE SWOOSH',53,2),('CREDITS HANDOFF',62,7),('CPU LOCATOR',71,3),
       ('RAM LOCATOR',102,3),('DISPLAY MEMORY',118,3),('CLOSING CARD',170,3)]

def render(capture):
    result=json.loads((capture/'result.json').read_text())
    if result.get('dos_exit')!='PASS':raise ValueError('Review requires a successful capture')
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:raise RuntimeError('ffmpeg is required for the review reel')
    preview=HERE/'build/robotron-preview.mp4'
    subprocess.run([sys.executable,str(HERE/'preview.py'),str(capture),'--output',str(preview)],check=True)
    assets=capture/'review-assets';assets.mkdir(exist_ok=True)
    command=[ffmpeg,'-v','error','-y','-i',str(preview)]
    font=ImageFont.load_default(size=19)
    for i,(name,start,duration) in enumerate(SHOTS):
        label=Image.new('RGBA',(640,480));draw=ImageDraw.Draw(label)
        draw.rectangle((0,0,639,28),fill=(0,0,0,230));draw.text((10,4),name,fill='white',font=font)
        path=assets/f'label-{i}.png';label.save(path)
        command+=['-loop','1','-i',str(path)]
    filters=[]
    for i,(name,start,duration) in enumerate(SHOTS):
        filters.append(f'[0:v]trim=start={start}:duration={duration},setpts=PTS-STARTPTS[v{i}]')
        filters.append(f'[v{i}][{i+1}:v]overlay=shortest=1:format=auto,format=yuv420p[out{i}]')
        filters.append(f'[0:a]atrim=start={start}:duration={duration},asetpts=PTS-STARTPTS[a{i}]')
    filters.append(''.join(f'[out{i}][a{i}]' for i in range(len(SHOTS)))+
                   f'concat=n={len(SHOTS)}:v=1:a=1[v][a]')
    video=capture/'review.mp4'
    command+=['-filter_complex',';'.join(filters),'-map','[v]','-map','[a]',
              '-c:v','libx264','-preset','fast','-crf','20','-c:a','aac','-b:a','160k',
              '-movflags','+faststart',str(video)]
    subprocess.run(command,check=True)
    sheet=Image.new('RGB',(960,((len(SHOTS)+2)//3)*264),'black');draw=ImageDraw.Draw(sheet)
    for i,(name,start,duration) in enumerate(SHOTS):
        frame=assets/f'frame-{i}.png'
        subprocess.run([ffmpeg,'-v','error','-y','-ss',str(54.2 if name=='DRONE SWOOSH' else 67.0 if name=='CREDITS HANDOFF' else start+duration/2),'-i',str(preview),
                        '-frames:v','1',str(frame)],check=True)
        x=(i%3)*320;y=(i//3)*264
        sheet.paste(Image.open(frame).convert('RGB').resize((320,240)),(x,y+24))
        draw.text((x+5,y+3),name,fill='white',font=ImageFont.load_default(size=14))
    sheet.save(capture/'review.png')
    (capture/'review.json').write_text(json.dumps({'shots':SHOTS,'validation':result},indent=2)+'\n')
    for src,dst in [(video,HERE/'build/robotron-review.mp4'),(capture/'review.png',HERE/'build/robotron-review.png')]:
        shutil.copyfile(src,dst)
    print(f'Review reel: {video}\nContact sheet: {capture / "review.png"}')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('capture',type=Path)
    render(parser.parse_args().capture.resolve())
