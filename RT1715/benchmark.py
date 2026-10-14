#!/usr/bin/env python3
"""Uncapped fixed-pose benchmark in an isolated headless DOSBox-X runtime."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import build


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--label',default='candidate')
    p.add_argument('--cycles',type=int,default=300000)
    p.add_argument('--reference',type=Path,help='Compare frame hashes and timings with this result.json')
    args=p.parse_args()
    if args.cycles<=0:p.error('Cycles must be positive')
    source=build.HERE/'build/dos'
    out=build.HERE/'build/pose-benchmarks'/f'{datetime.now():%Y%m%d-%H%M%S}-{args.label}'
    out.mkdir(parents=True)
    for asset in source.glob('U2E.*'):shutil.copyfile(asset,out/asset.name)
    (out/'PM.CFG').write_text('ram\n')
    (out/'BENCH.BAT').write_bytes(b'@echo off\r\nconfig -get cpu cycles > CPU.TXT\r\nU2E.EXE /bench > RUN.LOG\r\nif errorlevel 1 goto fail\r\necho PASS > RESULT.TXT\r\ngoto done\r\n:fail\r\necho FAIL > RESULT.TXT\r\n:done\r\nexit\r\n')
    command=[build.tool('dosbox-x'),'-conf',str(build.HERE/'dosbox-x.conf'),'-noautoexec','-fastlaunch',
             '-set',f'cpu cycles=fixed {args.cycles}','-c',f'mount c "{out}"','-c','c:','-c','bench.bat']
    print(out,flush=True)
    with (out/'dosbox.log').open('w') as log:
        proc=subprocess.Popen(command,env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:proc.wait(timeout=180)
        except BaseException:proc.kill();proc.wait();raise
    if proc.returncode or not (out/'RESULT.TXT').exists() or (out/'RESULT.TXT').read_text().strip()!='PASS':
        raise SystemExit('Benchmark failed; inspect '+str(out))
    log=(out/'BENCH.LOG').read_text()
    if not log.endswith('PASS\n'):raise SystemExit('Incomplete pose suite')
    rows=[]
    for line in log.splitlines():
        if line.startswith('POSE '):
            row={'frame':int(line.split()[1])}
            row.update({k:(v if k=='color' else int(v)) for k,v in re.findall(r'(\w+)=(\w+)',line)})
            row['milliseconds_per_render']=round(row['ticks']*1000/row['hz']/row['iterations'],3)
            rows.append(row)
    scene=hashlib.sha256()
    for asset in sorted(out.glob('U2E.*')):
        if asset.suffix.upper()!='.EXE':scene.update(asset.name.encode()+b'\0'+asset.read_bytes())
    result={'label':args.label,'cpu_cycles':(out/'CPU.TXT').read_text().strip(),
            'scene_sha256':scene.hexdigest(),'renderer_sha256':hashlib.sha256((out/'U2E.EXE').read_bytes()).hexdigest(),'poses':rows}
    if result['cpu_cycles']!=f'fixed {args.cycles}':raise SystemExit('CPU setting differs')
    if args.reference:
        ref=json.loads(args.reference.read_text())
        assert ref['cpu_cycles']==result['cpu_cycles'] and ref['scene_sha256']==result['scene_sha256']
        assert len(rows)==len(ref['poses'])==6
        for row,old in zip(rows,ref['poses']):
            assert row['frame']==old['frame'] and row['color']==old['color'],f"Visual mismatch at {row['frame']}"
            row['time_change_percent']=round((row['ticks']/old['ticks']-1)*100,2)
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
