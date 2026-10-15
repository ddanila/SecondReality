#!/usr/bin/env python3
"""Check the complete DOS bake audit and exercise live fallback in headless DOS."""
import argparse,hashlib,json,os,shutil,struct,subprocess
from datetime import datetime
from pathlib import Path
import build


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--audit',type=Path,required=True)
    p.add_argument('--dos-dir',type=Path,default=build.HERE/'build/dos');a=p.parse_args()
    native=json.loads((build.HERE/'build/baked/result.json').read_text());expected={r['frame']:r['color'] for r in native}
    actual={int(f):h for f,h in (line.split() for line in (a.audit/'HASH.LOG').read_text().splitlines())}
    if actual!=expected:raise ValueError('DOS projected route differs from native bake')
    reference=json.loads((build.HERE/'assets/robotron/motion-regression.json').read_text())['frames']
    compared=[r for r in native if str(r['frame']) in reference]
    if any(r['ppm_sha256']!=reference[str(r['frame'])] for r in compared):raise ValueError('Bake differs from original motion references')
    out=build.HERE/'build/bake-verification'/datetime.now().strftime('%Y%m%d-%H%M%S');out.mkdir(parents=True)
    source=a.dos_dir/'U2E.BKC'
    with source.open('rb') as f:
        head=f.read(24);frames=struct.unpack_from('<I',head,12)[0];base=28+frames*12
        f.seek(0);header=f.read(base);offsets=struct.unpack_from(f'<{frames+1}I',header,24)
        row=420//2-1;start=base+offsets[row];f.seek(start);block=bytearray(f.read(offsets[row+1]-offsets[row]))
    result={'dos_poses':len(actual),'original_reference_poses':len(compared),'different_poses':0,'fallback':{}}
    want=next(r['ppm_sha256'] for r in native if r['frame']==420)
    for case in ('missing','stale','corrupt'):
        dest=out/case;dest.mkdir()
        for asset in a.dos_dir.glob('U2E.*'):
            if asset.suffix!='.BKC':shutil.copyfile(asset,dest/asset.name)
        if case=='stale':
            stale=bytearray(head);stale[4]^=1;(dest/'U2E.BKC').write_bytes(stale)
        elif case=='corrupt':
            bad=bytearray(block);bad[len(bad)//2]^=1
            # Sparse backing preserves a valid index/length without copying
            # every unaffected pose just to corrupt this single test block.
            with (dest/'U2E.BKC').open('wb') as f:
                f.truncate(source.stat().st_size);f.write(header);f.seek(start);f.write(bad)
        (dest/'PM.CFG').write_text('ram\n');(dest/'VISUAL.PTS').write_text('420\n')
        (dest/'CHECK.BAT').write_bytes(b'@echo off\r\nU2E.EXE /visual > RUN.LOG\r\nif errorlevel 1 goto fail\r\necho PASS > RESULT.TXT\r\ngoto done\r\n:fail\r\necho FAIL > RESULT.TXT\r\n:done\r\nexit\r\n')
        with (dest/'dosbox.log').open('w') as log:
            subprocess.run([build.tool('dosbox-x'),'-conf',str(build.HERE/'dosbox-x.conf'),'-noautoexec','-fastlaunch','-c',f'mount c "{dest}"','-c','c:','-c','check.bat'],env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
        if (dest/'RESULT.TXT').read_text().strip()!='PASS':raise ValueError(case+' failed')
        digest=hashlib.sha256((dest/'P0420.PPM').read_bytes()).hexdigest()
        if digest!=want or 'BAKED hits=0 ' not in (dest/'BENCH.LOG').read_text():raise ValueError(case+' did not render through live fallback')
        result['fallback'][case]='PASS: live rendering matches original pixels'
    (out/'result.json').write_text(json.dumps(result,indent=2)+'\n');print(out);print(json.dumps(result,indent=2))

if __name__=='__main__':main()
