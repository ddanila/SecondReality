#!/usr/bin/env python3
"""Render fixed DOS poses and compare them with reviewed reference images.

--accept explicitly replaces the baseline; ordinary checks never update it.
A successful full playback supplies the actual first credit screen.
"""
import argparse
from datetime import datetime
import hashlib,json,os,shutil,subprocess
from pathlib import Path
from PIL import Image,ImageChops,ImageDraw
import build
import animation

HERE=Path(__file__).resolve().parent
SHOTS={'key-close-650':650,'key-close-660':660,'key-close-670':670,'key-close-680':680,
       'key-channel':700,'disk-inserting':1732,'disk-seated':1822,'lever-closed':1926,
       'boot-loader':2242,'boot-startup':2662,'boot-prompt':2802,'swoosh':3344,'handoff':3992}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dos-dir',type=Path,default=HERE/'build/dos')
    parser.add_argument('--capture',type=Path,required=True)
    parser.add_argument('--baseline',type=Path,default=HERE/'assets/robotron/regression')
    parser.add_argument('--accept',action='store_true')
    args=parser.parse_args();result=json.loads((args.capture/'result.json').read_text())
    if result.get('dos_exit')!='PASS':raise ValueError('Use a successful headless playback')
    for name in ('CRED.EXE','CARD01.CRD','CRED.IDX','CRED.CUE','CRED.TIM'):
        expected=result.get('runtime_sha256',{}).get(name)
        if not expected or hashlib.sha256((args.dos_dir/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('Credit capture does not match current runtime: '+name)
    out=HERE/'build/visual-regressions'/datetime.now().strftime('%Y%m%d-%H%M%S');out.mkdir(parents=True)
    for p in args.dos_dir.glob('U2E.*'):
        if p.suffix=='.BKC':
            try:os.link(p,out/p.name)
            except OSError:shutil.copyfile(p,out/p.name)
        else:shutil.copyfile(p,out/p.name)
    (out/'PM.CFG').write_text('ram\n');(out/'VISUAL.PTS').write_text('\n'.join(map(str,SHOTS.values()))+'\n')
    (out/'CHECK.BAT').write_bytes(b'@echo off\r\nU2E.EXE /visual > RUN.LOG\r\nif errorlevel 1 goto fail\r\necho PASS > RESULT.TXT\r\ngoto done\r\n:fail\r\necho FAIL > RESULT.TXT\r\n:done\r\nexit\r\n')
    command=[build.tool('dosbox-x'),'-conf',str(HERE/'dosbox-x.conf'),'-noautoexec','-fastlaunch',
             '-set','cpu cycles=fixed 300000','-c',f'mount c "{out}"','-c','c:','-c','check.bat']
    with (out/'dosbox.log').open('w') as log:
        subprocess.run(command,env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),stdout=log,stderr=subprocess.STDOUT,check=True,timeout=90)
    if (out/'RESULT.TXT').read_text().strip()!='PASS':raise RuntimeError('DOS visual capture failed')
    for name,frame in SHOTS.items():
        with Image.open(out/f'P{frame:04}.PPM') as im:im.save(out/(name+'.png'))
    def duration(path):
        return float(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','csv=p=0',str(path)]))
    credit=max((args.capture/name for name in result['video_files']),key=duration)
    subprocess.run(['ffmpeg','-v','error','-i',str(credit),'-ss','68.0','-frames:v','1','-vf','scale=320:200:flags=neighbor',str(out/'credit-handoff.png')],check=True)
    names=[*SHOTS,'credit-handoff'];report={'accepted':args.accept,'credit_sample_seconds':68.0,'capture':args.capture.name,'poses':SHOTS,'images':{},'runtime_sha256':hashlib.sha256((out/'U2E.EXE').read_bytes()).hexdigest()}
    slots=animation.mapping((out/'U2E.00M').read_bytes())[1:]
    inputs=['U2E.00M','U2E.0AB','U2E.AA','U2E.PRS','U2E.VIS',
            'CRED.EXE','CARD01.CRD','CRED.IDX','CRED.SYN','CRED.CUE','CRED.TIM']
    if (args.dos_dir/'U2E.BKC').exists():inputs.append('U2E.BKC')
    inputs += [f'U2E.{slot:03}' for slot in sorted(set(slots))]
    report['asset_sha256']={name:hashlib.sha256((args.dos_dir/name).read_bytes()).hexdigest() for name in inputs}
    sheet=Image.new('RGB',(960,240*((len(names)+2)//3)));draw=ImageDraw.Draw(sheet)
    failed=[]
    for i,name in enumerate(names):
        path=out/(name+'.png');im=Image.open(path).convert('RGB');sheet.paste(im,(i%3*320,i//3*240));draw.text((i%3*320,i//3*240+205),name,fill='white')
        reference=args.baseline/path.name
        if args.accept:
            args.baseline.mkdir(parents=True,exist_ok=True);shutil.copyfile(path,reference)
        if not reference.is_file():failed.append(name);report['images'][name]={'error':'missing baseline'};continue
        with Image.open(reference) as ref:
            diff=ImageChops.difference(im,ref.convert('RGB'));changed=sum(any(pixel) for pixel in diff.getdata())
        report['images'][name]={'changed_pixels':changed,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}
        if changed:failed.append(name);diff.save(out/(name+'-diff.png'))
    sheet.save(out/'contact.png');report['passed']=not failed
    (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    if args.accept:(args.baseline/'manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print(out);print('PASS' if not failed else 'FAIL: '+', '.join(failed))
    if failed:raise SystemExit(1)

if __name__=='__main__':main()
