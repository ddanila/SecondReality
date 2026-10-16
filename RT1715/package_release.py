#!/usr/bin/env python3
"""Package the tested DOS runtime with reproducible file hashes and provenance."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
import animation

HERE=Path(__file__).resolve().parent;ROOT=HERE.parent

def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--capture',type=Path,required=True)
    p.add_argument('--visual',type=Path,required=True)
    p.add_argument('--dos-dir',type=Path,default=HERE/'build/dos')
    p.add_argument('--output',type=Path,default=HERE/'build/releases')
    p.add_argument('--model-source',type=Path,default=ROOT.parent/'3d-models/models/robotron-1715m')
    args=p.parse_args();dos=args.dos_dir.resolve()
    capture=json.loads((args.capture/'result.json').read_text());visual=json.loads((args.visual/'result.json').read_text())
    if capture.get('dos_exit')!='PASS' or not visual.get('passed'):raise ValueError('Successful playback and visual checks required')
    if capture['renderer_sha256']!=digest(dos/'U2E.EXE') or visual['runtime_sha256']!=digest(dos/'U2E.EXE'):
        raise ValueError('Validation used a different renderer')
    if not visual.get('asset_sha256'):raise ValueError('Visual check must record input hashes')
    for name,expected in visual['asset_sha256'].items():
        if digest(dos/name)!=expected:raise ValueError('Visual input changed since comparison: '+name)
    # run.py hashes every U2E asset, including optional quality/cache files.
    scene=hashlib.sha256()
    for asset in sorted(dos.glob('U2E.*')):
        if asset.suffix.upper()!='.EXE':scene.update(asset.name.encode()+b'\0'+asset.read_bytes())
    if capture['scene_sha256']!=scene.hexdigest():raise ValueError('Scene changed since playback')
    for name,expected in capture.get('runtime_sha256',{}).items():
        if digest(dos/name)!=expected:raise ValueError('Runtime changed since playback: '+name)
    if not capture.get('runtime_sha256'):raise ValueError('Playback must record complete runtime hashes')
    # Freeze the exact contract used for this capture. Legacy captures are
    # revalidated before adopting today's contract rather than being relabelled.
    from chapters import DEFAULT, verify_logs
    contract = args.capture/'chapters.json'
    if not contract.exists():
        if capture.get('chapter_contract_sha256'):
            raise ValueError('Capture chapter contract is missing')
        contract = DEFAULT
    if capture.get('chapter_contract_sha256') and digest(contract) != capture['chapter_contract_sha256']:
        raise ValueError('Capture chapter contract changed')
    verify_logs({'flight': (args.capture/'flight.log').read_text(),
                 'credits': (args.capture/'credits.log').read_text()}, contract)
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    dirty=bool(subprocess.check_output(['git','status','--porcelain','--untracked-files=normal'],cwd=ROOT,text=True).strip())
    name='rt1715-'+commit[:8]+('-work' if dirty else '')
    out=args.output/name
    if out.exists():shutil.rmtree(out)
    out.mkdir(parents=True)
    shutil.copyfile(contract, out/'CHAPTERS.JSON')
    mapping=animation.mapping((dos/'U2E.00M').read_bytes())
    names=['RT1715.EXE','STARTMUS.EXE','U2E.EXE','CRED.EXE','REALITY.FC','U2E.00M','U2E.0AB','U2E.AA','U2E.PRS','U2E.VIS','CRED.IDX','CRED.SYN','CRED.CUE','CRED.TIM']
    if (dos/'FLIGHT.EXE').exists():names.append('FLIGHT.EXE')
    if (dos/'U2E.BKC').exists():names.append('U2E.BKC')
    names += [f'U2E.{slot:03}' for slot in sorted(set(mapping[1:]))]
    names += [line.split()[0] for line in (dos/'CRED.IDX').read_text().splitlines()[1:]]
    expansion=json.loads((dos/'EXPAND.JSON').read_text()) if (dos/'EXPAND.JSON').exists() else None
    if expansion:
        from expansion_checks import verify
        if expansion['cut'] not in ('expanded','extended'):raise ValueError('Use a full cut for a release')
        if capture.get('cut') != expansion['cut']:raise ValueError('Capture used a different cut')
        for key,filename in [('intro','fx.log'),('post','post.log')]:
            if expansion[key]:verify((args.capture/filename).read_text(),expansion[key])
        names += ['SHORT.EXE','EXPAND.JSON','FX.EXE','FX.TIM','FX.IMG','FX.FNT','FX.PTS','FX.GEO','FX.LOC','FX.CRT','FX.MSH','FX.DRW','FX.VIS','FXSOURCE.JSON']
        if expansion['post']:names += ['POST.EXE','POST.TIM']

    for name in names:shutil.copyfile(dos/name,out/name)
    (out/'PM.CFG').write_bytes(b'ram\r\n')
    config=(HERE/'dosbox-x.conf').read_text().replace('mount c build/dos','mount c .')
    (out/'RT1715.CON').write_text(config+'\nexit\n')
    (out/'HEADLESS.SH').write_text('#!/bin/sh\nset -eu\ncd "$(dirname "$0")"\nexport SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy\nexec dosbox-x -conf RT1715.CON -fastlaunch\n');(out/'HEADLESS.SH').chmod(0o755)
    (out/'HEADLESS.BAT').write_bytes(b'@echo off\r\nset SDL_VIDEODRIVER=dummy\r\nset SDL_AUDIODRIVER=dummy\r\ndosbox-x -conf RT1715.CON -fastlaunch\r\n')
    (out/'README.TXT').write_text('''ROBOTRON 1715M - SECOND REALITY EXTRACT

Unzip to a writable directory. From DOS, run RT1715.EXE.
From the extracted directory on a host with DOSBox-X installed:
  dosbox-x -conf RT1715.CON -fastlaunch
For unattended headless playback, run HEADLESS.SH (macOS/Linux) or
HEADLESS.BAT (Windows). Both disable video/audio windows and exit automatically.
No guest compiler, model files, firmware or disk image is needed.

Controls: Escape exits. Playback runs once, about 175 seconds, then returns.
Sound is fixed to Sound Blaster Pro: port 220h, IRQ 7, DMA 1 (T4).
Tested emulator profile: 486 dynamic core, VGA, 32 MB, XMS/EMS/UMB enabled,
fixed 300000 cycles. Slower profiles work but reduce motion smoothness.
These are tested emulator settings, not a real-hardware minimum claim.
The 32-bit renderer includes DOS/32A. Run the launcher, not U2E.EXE alone.

Original drone, music and Second Reality material: Future Crew.
Robotron source-model and component attribution/licences: NOTICES/.
Boot imagery is captured from DAC's S550/TOS-M reference system; display and
activity timing are compressed for the demo. This is not an OS emulator.

TECHNICAL-SOURCES.TXT and CLAIMS.JSON map each credit line to its evidence,
with specimen observations separated from reference configurations.
PROVENANCE.JSON records source, toolchain, media and validation identities.
SHA256SUMS lists every packaged file except itself. No captures, debug logs,
bench executables, sibling disk images or optional experiment settings ship.
''')
    if expansion:
        readme=out/'README.TXT'
        text=readme.read_text().replace('about 175 seconds',f"about {round(capture['wall_seconds'])} seconds")
        text += ('\nCut: '+expansion['cut']+'. The added chapters are live DOS effects.\n'
                 'EXPAND.JSON records their tracker cues; FXSOURCE.JSON records model assets.\n'
                 'Run SHORT.EXE for flight + credits; FLIGHT.EXE for flight only.\n'
                 'Signal flow and separated source boards are explanatory views.\n'
                 'These effects do not represent graphics generated by the Robotron CPU.\n')
        readme.write_text(text)
    from claim_index import export as export_claims
    export_claims(out)
    notices=out/'NOTICES';notices.mkdir()
    shutil.copyfile(ROOT/'README.md',notices/'SECOND-REALITY.txt')
    for src,dst in [(args.model_source/'LICENSE','MODEL-LICENSE.txt'),(HERE/'assets/robotron/SOURCES.txt','SOURCES.txt'),(HERE/'assets/robotron/KICAD-NOTICE.txt','KICAD-NOTICE.txt')]:shutil.copyfile(src,notices/dst)
    shutil.copytree(HERE/'assets/licenses',notices/'TOOLCHAIN')
    # Keep the component sources with their embedded per-file notices and exceptions.
    shutil.copytree(args.model_source/'components/kicad/source',notices/'KICAD-SOURCES')
    source_paths=[*HERE.glob('*.py'),*HERE.glob('*.c'),*HERE.glob('*.h'),*HERE.glob('*.asm'),*HERE.glob('*.INC'),*list((HERE/'assets/robotron').rglob('*'))]
    source_hashes={str(path.relative_to(ROOT)):digest(path) for path in sorted(source_paths) if path.is_file()}
    provenance={'git_commit':commit,'dirty_worktree':dirty,'source_sha256':source_hashes,
                'toolchain':json.loads((HERE/'build/renderer32/toolchain.json').read_text()),
                'model_build':json.loads((HERE/'build/robotron/report.json').read_text()),
                'boot':json.loads((HERE/'assets/robotron/boot/provenance.json').read_text()),
                'playback':capture,'visual':visual,
                'packaged_runtime_sha256':{name:digest(out/name) for name in sorted(set(names))}}
    (out/'PROVENANCE.JSON').write_text(json.dumps(provenance,indent=2).replace(str(ROOT.parent)+'/', '')+'\n')
    files=sorted(path for path in out.rglob('*') if path.is_file())
    (out/'SHA256SUMS').write_text(''.join(f'{digest(path)}  {path.relative_to(out).as_posix()}\n' for path in files))
    archive=out.with_suffix('.zip')
    with zipfile.ZipFile(archive,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for path in sorted(out.rglob('*')):
            if path.is_file():
                info=zipfile.ZipInfo(path.relative_to(out).as_posix(),(2026,10,15,0,0,0));info.external_attr=(path.stat().st_mode&0xffff)<<16;info.compress_type=zipfile.ZIP_DEFLATED
                z.writestr(info,path.read_bytes())
    archive.with_suffix('.zip.sha256').write_text(digest(archive)+'  '+archive.name+'\n')
    print(archive);print(out)

if __name__=='__main__':main()
