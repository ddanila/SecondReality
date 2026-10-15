#!/usr/bin/env python3
"""Measure unchanged-image holds during the moving close flyover in DOS capture."""
import argparse
from fractions import Fraction
import json
from pathlib import Path
import subprocess


def measure(capture,start=8,end=46):
    result=json.loads((capture/'result.json').read_text())
    if result['dos_exit']!='PASS':raise ValueError('Capture must have completed successfully')
    offset=0;main=None
    for video in sorted(capture.glob('*.avi')):
        duration=float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration',
                                               '-of','default=nw=1:nk=1',str(video)],text=True))
        if offset<=start and end<=offset+duration:main=video;break
        offset+=duration
    if main is None:raise ValueError('Measurement window must lie within one captured video segment')
    hashes=subprocess.check_output(['ffmpeg','-v','error','-i',str(main),'-vf',
        f'trim=start={start-offset}:end={end-offset},setpts=PTS-STARTPTS',
        '-an','-fps_mode','passthrough','-f','framemd5','-'],text=True)
    timebase=None;previous=None;hold=0;holds=[];frames=0
    for line in hashes.splitlines():
        if line.startswith('#tb 0:'):timebase=Fraction(line.split(':',1)[1].strip())
        if line.startswith('#') or not line.strip():continue
        fields=[s.strip() for s in line.split(',')];digest=fields[-1];duration=int(fields[3])
        if previous is not None and digest!=previous:holds.append(hold);hold=0
        hold+=duration;previous=digest;frames+=1
    if hold:holds.append(hold)
    if not holds or timebase is None:raise ValueError('No video frames decoded')
    milliseconds=sorted(float(h*timebase*1000) for h in holds)
    return {'window_seconds':[start,end],'cpu_cycles':result['cpu_cycles'],
            'captured_frames':frames,'unique_image_runs':len(holds),
            'mean_image_hold_ms':round(sum(milliseconds)/len(milliseconds),2),
            'p95_image_hold_ms':round(milliseconds[int((len(milliseconds)-1)*.95)],2),
            'max_image_hold_ms':round(max(milliseconds),2),
            'holds_over_100_ms':sum(ms>100 for ms in milliseconds)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('capture',type=Path)
    print(json.dumps(measure(parser.parse_args().capture),indent=2))
