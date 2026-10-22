#!/usr/bin/env python3
"""Capture a full-demo review build unattended, retaining source frame rates."""
import argparse
from datetime import datetime
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import time
from full_demo import read_trace
from build import HERE


def capture(dos, output=None, timeout=1200, cycles=300000):
    dos=Path(dos).resolve()
    if not (dos/'FULL.EXE').is_file(): raise ValueError('Missing FULL.EXE in '+str(dos))
    output=Path(output or HERE/'capture'/('full-'+datetime.now().strftime('%Y%m%d-%H%M%S'))).resolve()
    output.mkdir(parents=True,exist_ok=False)
    for name in ('RESULT.TXT','SCENES.BIN'): (dos/name).unlink(missing_ok=True)
    batch='''@echo off
set BLASTER=A220 I7 D1 T4
dx-capture /V /A /-D full.exe > DEMO.LOG
if errorlevel 1 goto failed
echo PASS > RESULT.TXT
goto done
:failed
echo FAIL > RESULT.TXT
:done
exit
'''
    (dos/'RUNTEST.BAT').write_bytes(batch.replace('\n','\r\n').encode('ascii'))
    cmd=[shutil.which('dosbox-x') or 'dosbox-x','-conf',str(HERE/'dosbox-x.conf'),'-noautoexec','-fastlaunch',
         '-set',f'cpu cycles=fixed {cycles}','-set',f'dosbox captures={output}',
         '-c',f'mount c "{dos}"','-c','c:','-c','runtest.bat']
    (output/'capture-manifest.json').write_text(json.dumps({
        'runtime':str(dos),'cycles':cycles,'headless':True,
        'config_sha256':hashlib.sha256((HERE/'dosbox-x.conf').read_bytes()).hexdigest(),
        'files':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dos.iterdir())
                 if p.is_file() and p.suffix.upper()!='.LOG' and p.name not in ('RESULT.TXT','RUNTEST.BAT','SCENES.BIN')}
    },indent=2)+'\n')
    print(output,flush=True)
    with (output/'dosbox.log').open('w') as log:
        proc=subprocess.Popen(cmd,cwd=HERE,env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        deadline=time.monotonic()+timeout
        try:
            while True:
                try:
                    code=proc.wait(timeout=min(1,max(.01,deadline-time.monotonic())))
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic()>=deadline:raise
                    log.flush()
                    # A divide-error loop must not fill the host disk with logs.
                    with (output/'dosbox.log').open('rb') as check:
                        check.seek(max(0,(output/'dosbox.log').stat().st_size-8192))
                        tail=check.read()
                    if b'Illegal Unhandled Interrupt' in tail:
                        raise RuntimeError('DOS CPU exception; see dosbox.log')
        except BaseException as error:
            proc.kill();proc.wait()
            (output/'result.json').write_text(json.dumps({'dos_exit':'FAIL','error':str(error),'cycles':cycles},indent=2)+'\n')
            raise
    if code or not (dos/'RESULT.TXT').exists() or (dos/'RESULT.TXT').read_text().strip()!='PASS':
        error='DOS playback failed; inspect '+str(output/'dosbox.log')
        (output/'result.json').write_text(json.dumps({'dos_exit':'FAIL','error':error,'cycles':cycles},indent=2)+'\n')
        raise RuntimeError(error)
    entries=read_trace(dos/'SCENES.BIN')
    if not entries or len(entries)%2: raise RuntimeError('Incomplete scene trace')
    for a,b in zip(entries[::2],entries[1::2]):
        if a['phase']!='entry' or b['phase']!='exit' or a['executable']!=b['executable']:raise RuntimeError('Unpaired scene trace')
    videos=sorted(output.glob('*.avi'),key=lambda p:p.stat().st_mtime_ns)
    for i,p in enumerate(videos):p.rename(output/f'segment-{i:03}.tmp')
    for i in range(len(videos)):(output/f'segment-{i:03}.tmp').rename(output/f'full_{i:03}.avi')
    (output/'scenes.json').write_text(json.dumps(entries,indent=2)+'\n')
    shutil.copyfile(dos/'SCENES.BIN',output/'SCENES.BIN')
    (output/'result.json').write_text(json.dumps({'dos_exit':'PASS','cycles':cycles,'scenes':entries},indent=2)+'\n')
    return output

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('dos',type=Path);p.add_argument('--output',type=Path);p.add_argument('--timeout',type=int,default=1200);p.add_argument('--cycles',type=int,default=300000)
    a=p.parse_args();capture(a.dos,a.output,a.timeout,a.cycles)
