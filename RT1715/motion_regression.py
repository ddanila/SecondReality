#!/usr/bin/env python3
"""Review and hash continuous DOS keyboard, monitor and swoosh sequences.

A normal run never changes references. After reviewing its films/contact sheets,
--accept-from PATH accepts that run only if it still matches the current assets.
"""
import argparse
import io
import time
from datetime import datetime
import hashlib,json,os,shutil,subprocess,zipfile
from contextlib import nullcontext
from pathlib import Path
from PIL import Image,ImageDraw
import build

HERE=Path(__file__).resolve().parent
WINDOWS={'keyboard':(2,1680),'drive':(1682,1960),'monitor':(2030,3150),'swoosh':(3220,3450),'screen-return':(3452,4062)}
BASELINE=HERE/'assets/robotron/motion-regression.json'

def hashes(dos):
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dos.glob('U2E.*'))}

def archive_frames(out):
    frames=list(out.glob('P*.PPM'))
    with zipfile.ZipFile(out/'frames.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
        for p in frames:archive.write(p,p.name)
    with zipfile.ZipFile(out/'frames.zip') as archive:
        if len(archive.namelist())!=len(frames) or archive.testzip() is not None:
            raise RuntimeError('Frame archive verification failed; raw frames retained')
    for p in frames:p.unlink()
    for p in out.glob('*/F*.PPM'):
        if p.is_symlink():p.unlink()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dos-dir',type=Path,default=HERE/'build/dos')
    parser.add_argument('--accept-from',type=Path)
    args=parser.parse_args()
    if args.accept_from:
        report=json.loads((args.accept_from/'result.json').read_text())
        required={str(f) for lo,hi in WINDOWS.values() for f in range(lo,hi+1,2)}
        if set(report['frames'])!=required:raise ValueError('Incomplete motion coverage')
        if report['assets']!=hashes(args.dos_dir):raise ValueError('Reviewed run does not match current runtime')
        packed=args.accept_from/'frames.zip'
        with zipfile.ZipFile(packed) if packed.exists() else nullcontext(None) as archive:
            for frame,digest in report['frames'].items():
                name=f'P{int(frame):04}.PPM';raw=args.accept_from/name
                data=raw.read_bytes() if raw.exists() else archive.read(name) if archive else b''
                if hashlib.sha256(data).hexdigest()!=digest:
                    raise ValueError('Reviewed frames were changed')
        BASELINE.write_text(json.dumps({'windows':WINDOWS,'frames':report['frames']},indent=2)+'\n')
        report.update(passed=True,accepted=True)
        (args.accept_from/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print('Accepted reviewed motion run:',args.accept_from);return
    if shutil.disk_usage(HERE).free<128*1024*1024:
        raise RuntimeError('Motion export needs at least 128 MiB free for streamed frames')
    out=HERE/'build/motion-regressions'/datetime.now().strftime('%Y%m%d-%H%M%S');out.mkdir(parents=True)
    frames=sorted({f for lo,hi in WINDOWS.values() for f in range(lo,hi+1,2)})
    for p in args.dos_dir.glob('U2E.*'):
        if p.suffix=='.BKC':
            try:os.link(p,out/p.name)
            except OSError:shutil.copyfile(p,out/p.name)
        else:shutil.copyfile(p,out/p.name)
    (out/'PM.CFG').write_text('ram\n');(out/'VISUAL.PTS').write_text('\n'.join(map(str,frames))+'\n')
    (out/'CHECK.BAT').write_bytes(b'@echo off\r\nU2E.EXE /visual > RUN.LOG\r\nif errorlevel 1 goto fail\r\necho PASS > RESULT.TXT\r\ngoto done\r\n:fail\r\necho FAIL > RESULT.TXT\r\n:done\r\nexit\r\n')
    print(out,flush=True)
    with (out/'dosbox.log').open('w') as log:
        process=subprocess.Popen([build.tool('dosbox-x'),'-conf',str(HERE/'dosbox-x.conf'),'-noautoexec','-fastlaunch',
            '-c',f'mount c "{out}"','-c','c:','-c','check.bat'],
            env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),stdout=log,stderr=subprocess.STDOUT)
        # A successor file is created only after the previous PPM is closed.
        # Compress completed frames immediately, keeping disk use bounded.
        index=0;deadline=time.monotonic()+600
        try:
            with zipfile.ZipFile(out/'frames.zip','w',zipfile.ZIP_DEFLATED,compresslevel=6) as archive:
                while index<len(frames):
                    done=process.poll() is not None
                    current=out/f'P{frames[index]:04}.PPM'
                    successor=(out/f'P{frames[index+1]:04}.PPM') if index+1<len(frames) else None
                    if current.exists() and (done or (successor and successor.exists())):
                        data=current.read_bytes()
                        if len(data)!=192015 or not data.startswith(b'P6\n320 200\n255\n'):
                            raise RuntimeError('Incomplete DOS frame: '+current.name)
                        archive.writestr(current.name,data);current.unlink();index+=1
                    elif done:raise RuntimeError('Missing DOS frame: '+current.name)
                    else:
                        if time.monotonic()>deadline:raise TimeoutError('Motion export exceeded 600 seconds')
                        time.sleep(.02)
            if process.wait(timeout=10):raise RuntimeError('DOSBox motion export failed')
        finally:
            if process.poll() is None:process.kill();process.wait()
    if (out/'RESULT.TXT').read_text().strip()!='PASS':raise RuntimeError('Motion export failed')
    report={'windows':WINDOWS,'assets':hashes(out),'frames':{},'accepted':False}
    with zipfile.ZipFile(out/'frames.zip') as archive:
        for f in frames:report['frames'][str(f)]=hashlib.sha256(archive.read(f'P{f:04}.PPM')).hexdigest()
    expected=json.loads(BASELINE.read_text()) if BASELINE.exists() else {}
    report['changed_frames']=[f for f,h in report['frames'].items() if expected.get('frames',{}).get(f)!=h]
    report['passed']=(not report['changed_frames'] and
        set(expected.get('frames',{}))==set(report['frames']) and
        expected.get('windows')=={k:list(v) for k,v in WINDOWS.items()})
    with zipfile.ZipFile(out/'frames.zip') as archive:
        if archive.testzip() is not None:raise RuntimeError('Frame archive CRC failed')
        for name,(lo,hi) in WINDOWS.items():
            selected=list(range(lo,hi+1,2))
            encoder=subprocess.Popen(['ffmpeg','-v','error','-y','-f','image2pipe','-vcodec','ppm',
                '-framerate','35','-i','-', '-vf','scale=640:400:flags=neighbor',
                '-c:v','libx264','-crf','18','-pix_fmt','yuv420p',str(out/(name+'.mp4'))],stdin=subprocess.PIPE)
            try:
                for f in selected:encoder.stdin.write(archive.read(f'P{f:04}.PPM'))
                encoder.stdin.close()
                if encoder.wait():raise RuntimeError('Motion film encoding failed')
            finally:
                if encoder.poll() is None:encoder.kill();encoder.wait()
            sheet=Image.new('RGB',(1280,420));draw=ImageDraw.Draw(sheet)
            for i in range(8):
                f=selected[round(i*(len(selected)-1)/7)]
                with Image.open(io.BytesIO(archive.read(f'P{f:04}.PPM'))) as im:sheet.paste(im,(i%4*320,i//4*210))
                draw.text((i%4*320,i//4*210+200),f'{name} {f/70:.2f}s',fill='white')
            sheet.save(out/(name+'.png'))
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS' if report['passed'] else f"REVIEW REQUIRED: {len(report['changed_frames'])} changed/missing reference frames")
    if not report['passed']:raise SystemExit(1)

if __name__=='__main__':main()
