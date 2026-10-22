#!/usr/bin/env python3
"""Assemble an isolated full-demo work-in-progress runtime; preserve the short cut."""
import argparse,hashlib,json,shutil,subprocess
from pathlib import Path
from build import HERE,ROOT
import full_flyover,pm_renderer
import full_demo,full_opening,full_art,full_legacy,full_lens,full_space,full_plasma,full_water,full_scroll,full_terrain,full_credits


def unpack(name):
    source=ROOT/'MAIN/DATA'/name
    output=HERE/'build/full-release'/name.replace('.','-').replace('&','-')
    stamp=hashlib.sha256(source.read_bytes()).hexdigest()
    final=output/'plain/output.000.exe'
    if final.exists() and (output/'source.sha256').exists() and (output/'source.sha256').read_text()==stamp:return final
    deark=HERE/'build/toolchain/deark/deark'
    if not deark.is_file():raise RuntimeError('Build host Deark in RT1715/build/toolchain/deark first')
    for folder in ('pklite','plain'):
        p=output/folder;p.mkdir(parents=True,exist_ok=True)
        for old in p.glob('output.*'):old.unlink()
    if b'PKLITE' in source.read_bytes()[:256]:
        subprocess.run([str(deark),'-m','pklite','-od',str(output/'pklite'),str(source)],check=True)
    else:shutil.copyfile(source,output/'pklite/output.000.exe')
    subprocess.run([str(deark),'-opt','execomp','-od',str(output/'plain'),str(output/'pklite/output.000.exe')],check=True)
    if not final.exists():
        first=output/'pklite/output.000.exe'
        raw=first.read_bytes()
        if raw[:2]!=b'MZ' or b'LZ90' in raw[:64] or b'LZ91' in raw[:64]:
            raise ValueError('Release decompression failed')
        shutil.copyfile(first,final)
    (output/'source.sha256').write_text(stamp)
    return final


def build(output,stop_after=None):
    output=Path(output).resolve()
    if output==HERE/'build' or output==HERE/'build/dos' or (HERE/'build/dos') in output.parents:
        raise ValueError('The reviewed short build must remain isolated')
    dos=full_demo.build(output,stop_after,robotron=True)
    assets=[]
    assets.append(full_opening.build(output/'opening',unpack('ALKU.EXE')))
    for name in ('title','unicorn'):assets.append(full_art.build_picture(name,HERE/'build/full-art-built'/name))
    assets.append(full_art.monster(HERE/'build/full-art-built/monster'))
    for name,fn in [('keycap',full_legacy.keycap),('tunnel',full_legacy.tunnel),('interference',full_legacy.interference),('dots',full_legacy.dots),('terrain',full_terrain.build)]:assets.append(fn(output/name))
    assets.append(full_plasma.build(output/'plasma'))
    assets.extend(full_water.water(unpack('MNTSCRL.EXE'),output/'water'))
    assets.extend(full_water.tape(unpack('RAYSCRL.EXE'),output/'tape'))
    assets.append(full_scroll.build(output/'scroll'))
    assets.append(full_lens.build(unpack('LNS&ZOOM.EXE'),output/'lens'))
    space=full_space.build(output/'space');assets.append(full_space.patch_player(unpack('U2A.EXE'),output/'space'));assets.extend([space/'U2A.002',space/'U2A.003'])
    short=HERE/'build/dos'
    for pattern in ('U2E.*','CARD??.CRD','CRED.EXE','CRED.IDX','CRED.CUE','CRED.SYN','CRED.TIM','DOS4GW.EXE'):
        assets.extend(short.glob(pattern))
    for asset in assets:shutil.copyfile(asset,dos/asset.name)
    full_credits.build(dos)
    pm_renderer.build_renderer(output,watcom=HERE/"build/toolchain/watcom")
    full_flyover.build(dos)
    shutil.copyfile(HERE/'FULL-DEMO-PROGRESS.txt',dos/'RTINFO.TXT')
    (output/'runtime.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dos.iterdir()) if p.is_file()},indent=2)+'\n')
    (output/'status.json').write_text(json.dumps({'status':'work in progress; not the completed plan','drafts':['opening','space','title','keycap','tunnel','interference','monster','lens','dots','unicorn'],'preserved':['reviewed Robotron flyover and illustrated credits'],'still_original':[], 'new_drafts_pending_validation':['water','plasma','tape','terrain','scroll'],'timing':'continuous validation pending; do not present smoke tests as synchronized reviews'},indent=2)+'\n')
    return dos

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=HERE/'build/full-remake');p.add_argument('--stop-after',choices=('opening','space','title','keycap','tunnel','monster','water','lens','tape','unicorn'));a=p.parse_args();print(build(a.output,a.stop_after))
