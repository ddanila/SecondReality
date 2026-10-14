#!/usr/bin/env python3
"""Compare visible frame updates in completed, fixed-CPU DOS captures."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import re
import shutil
import subprocess

def counts(capture,windows):
    result=json.loads((capture/'result.json').read_text())
    if result.get('dos_exit')!='PASS':raise ValueError('Capture did not pass playback validation')
    cycles=result.get('cpu_cycles','')
    if not cycles.startswith('fixed '):raise ValueError('Comparison requires recorded fixed CPU cycles')
    # Segment 000 is the startup text mode; 001 is the flyover VGA recording.
    video=capture/'rt1715_001.avi'
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg:raise RuntimeError('ffmpeg is required')
    data=subprocess.check_output([ffmpeg,'-v','error','-i',str(video),'-t',str(max(windows)),
                                  '-map','0:v','-pix_fmt','rgb24','-f','framemd5','-'],text=True)
    timebase=Fraction(re.search(r'#tb 0:\s*(\S+)',data)[1])
    frames=[line.split(',') for line in data.splitlines() if line and not line.startswith('#')]
    if not frames or (int(frames[-1][2])+2*int(frames[-1][3]))*timebase<max(windows):
        raise ValueError('Capture is shorter than the requested comparison window')
    measured={}
    for seconds in windows:
        hashes=[row[-1].strip() for row in frames if int(row[2])*timebase<seconds]
        measured[str(seconds)]=sum(a!=b for a,b in zip(hashes,hashes[1:]))
    return result,measured

def compare(before,after,windows=(20,50)):
    a,old=counts(before,windows);b,new=counts(after,windows)
    if a['cpu_cycles']!=b['cpu_cycles']:raise ValueError('CPU settings differ')
    same_scene=None
    if a.get('scene_sha256') and b.get('scene_sha256'):
        same_scene=a['scene_sha256']==b['scene_sha256']
        if not same_scene:raise ValueError('Scene assets differ')
    return {'baseline':str(before),'candidate':str(after),'cpu_cycles':a['cpu_cycles'],
            'scene_hash_match':same_scene,
            'note':'RGB frame-change counts, not refresh rates; null scene match means older metadata lacks hashes.',
            'windows':{key:{'before':old[key],'after':new[key],
                           'change_percent':round((new[key]/old[key]-1)*100,2) if old[key] else None}
                       for key in old}}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('baseline',type=Path);parser.add_argument('candidate',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args();text=json.dumps(compare(args.baseline,args.candidate),indent=2)+'\n'
    if args.output:args.output.write_text(text)
    print(text,end='')
