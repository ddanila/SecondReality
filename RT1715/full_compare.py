#!/usr/bin/env python3
"""Music-aligned side-by-side review; never time-stretch either performance."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import numpy as np
from scipy.signal import correlate
from PIL import Image,ImageDraw,ImageFont


def audio(path):
    b=subprocess.check_output(['ffmpeg','-v','error','-i',str(path),'-vn','-ac','1','-ar','8000','-f','f32le','-'])
    return np.frombuffer(b,dtype='<f4').astype(np.float64)


def align(reference,remake,start,duration,max_shift=2.0):
    rate=8000;checks=[]
    for t in np.linspace(start+min(4,duration/8),start+duration-min(4,duration/8)-2,7):
        a=int(t*rate);n=rate*2;lo=max(0,a-int(max_shift*rate));hi=min(len(remake),a+n+int(max_shift*rate))
        x=reference[a:a+n];y=remake[lo:hi]
        if len(x)!=n or len(y)<n:raise ValueError('Audio ends before comparison interval')
        energy=float(x@x)
        if energy<1e-6:continue
        x=x-x.mean();corr=correlate(y,x,mode='valid',method='fft')
        energy_y=np.convolve(y*y,np.ones(1),mode='same')
        cumulative=np.concatenate(([0.],np.cumsum(energy_y)))
        denominators=np.sqrt(np.maximum(cumulative[n:]-cumulative[:-n],1e-20)*(x@x))
        scores=corr/denominators;k=int(np.argmax(scores))
        checks.append({'reference_seconds':float(t),'offset_seconds':(lo+k-a)/rate,'correlation':float(scores[k])})
    if len(checks)<3:raise ValueError('Not enough audible windows to establish synchronization')
    # A quiet fade or emulated mixer transient may weaken one window. Require
    # a strong majority, retain every measurement, and check drift across ALL
    # reliable windows rather than allowing weak matches to select the lag.
    for check in checks:check['reliable']=check['correlation']>=.65
    reliable=[c for c in checks if c['reliable']]
    if len(reliable)<max(3,len(checks)-2):raise ValueError('Soundtracks do not match reliably: '+str(checks))
    offsets=[c['offset_seconds'] for c in reliable]
    if max(offsets)-min(offsets)>1/70:raise ValueError('Music drift exceeds one VGA frame; do not hide it with retiming: '+str(checks))
    return float(np.median(offsets)),checks


def export(capture,output):
    capture=Path(capture);output=Path(output)
    temporary=output.with_name(output.stem+'.partial.mp4')
    videos=sorted(capture.glob('*.avi'));waves=list(capture.glob('*.wav'))
    if not videos or len(waves)!=1:raise ValueError('Need completed video segments and one continuous WAV')
    cmd=['ffmpeg','-v','error','-y']
    for p in videos+waves:cmd+=['-i',str(p)]
    filters=[f'[{i}:v]setpts=PTS-STARTPTS,scale=640:480:flags=neighbor,setsar=1,fps=70[v{i}]' for i in range(len(videos))]
    filters+=[''.join(f'[v{i}]' for i in range(len(videos)))+f'concat=n={len(videos)}:v=1:a=0[v]']
    cmd+=['-filter_complex',';'.join(filters),'-map','[v]','-map',f'{len(videos)}:a','-c:v','libx264','-threads','4','-preset','veryfast','-crf','18','-c:a','aac','-b:a','192k','-shortest','-movflags','+faststart',str(temporary)]
    subprocess.run(cmd,check=True)
    temporary.replace(output)


def compare(original,remake,output,start,duration,remake_start=None,alignment_window=None,left_label="ORIGINAL SECOND REALITY",right_label="ROBOTRON 1715 / REVIEW"):
    original=Path(original);remake=Path(remake);output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    oa=next(original.glob('*.wav'));ra=next(remake.glob('*.wav'))
    if remake_start is None:
        offset,checks=align(audio(oa),audio(ra),start,duration)
    else:
        # Independent scene captures may start at the same music cue on a
        # different timeline. Measure the lag; never stretch either recording.
        ref=audio(oa)[round(start*8000):]
        rem=audio(ra)[round(remake_start*8000):]
        lag,checks=align(ref,rem,*(alignment_window or (0,duration)))
        for c in checks:
            c['reference_seconds']+=start
            c['offset_seconds']+=remake_start-start
        offset=remake_start-start+lag
    for capture in (original,remake):
        if not (capture/'review-source.mp4').exists():export(capture,capture/'review-source.mp4')
    header=output.with_suffix('.header.png')
    im=Image.new('RGB',(1280,32),'black');d=ImageDraw.Draw(im);font=ImageFont.load_default(size=18)
    d.text((12,5),left_label,font=font,fill='white');d.text((652,5),right_label,font=font,fill='white');im.save(header)
    remake_seek=max(0,start+offset)
    missing_prefix=max(0,-start-offset)
    prefix=f'tpad=start_duration={missing_prefix}:start_mode=add:color=black,' if missing_prefix else ''
    filters=(f'[0:v]trim=duration={duration},setpts=PTS-STARTPTS,pad=640:512:0:32:black[l];'
             f'[1:v]setpts=PTS-STARTPTS,{prefix}trim=duration={duration},pad=640:512:0:32:black[r];'
             '[l][r]hstack=inputs=2[pair];[pair][3:v]overlay=shortest=1[v];'
             f'[2:a]atrim=duration={duration},asetpts=PTS-STARTPTS[a]')
    subprocess.run(['ffmpeg','-v','error','-y','-ss',str(start),'-i',str(original/'review-source.mp4'),'-ss',str(remake_seek),'-i',str(remake/'review-source.mp4'),'-ss',str(start),'-i',str(oa),'-loop','1','-i',str(header),'-filter_complex',filters,'-map','[v]','-map','[a]','-c:v','libx264','-threads','4','-preset','veryfast','-crf','18','-c:a','aac','-b:a','192k','-movflags','+faststart',str(output)],check=True)
    report={'original':str(original),'remake':str(remake),'reference_start':start,'duration':duration,'remake_offset':offset,'audio_checks':checks,'audio_source':str(oa),'time_stretch':False,'fps':70,'alignment_window':alignment_window,'remake_missing_prefix_seconds':missing_prefix,'labels':[left_label,right_label]}
    output.with_suffix('.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('original',type=Path);p.add_argument('remake',type=Path);p.add_argument('output',type=Path);p.add_argument('--start',type=float,default=0);p.add_argument('--duration',type=float,required=True);a=p.parse_args();print(json.dumps(compare(a.original,a.remake,a.output,a.start,a.duration),indent=2))
