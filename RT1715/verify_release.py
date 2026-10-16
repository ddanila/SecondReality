#!/usr/bin/env python3
"""Unpack and run the shipped headless launcher, using only release files."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import zipfile
from run import verify_sync,verify_card_schedule


def verify(archive,output,timeout=360):
    archive=Path(archive).resolve();output=Path(output)
    with tempfile.TemporaryDirectory(prefix='rt1715-release-') as directory:
        root=Path(directory)
        with zipfile.ZipFile(archive) as z:
            for item in z.infolist():
                path=Path(item.filename)
                if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe archive path')
            z.extractall(root)
        sums={}
        for line in (root/'SHA256SUMS').read_text().splitlines():
            expected,name=line.split('  ',1)
            actual=hashlib.sha256((root/name).read_bytes()).hexdigest()
            if expected!=actual:raise ValueError('Release hash mismatch: '+name)
            sums[name]=actual
        for name in ['README.TXT','NOTICES/SECOND-REALITY.txt','NOTICES/MODEL-LICENSE.txt',
                     'NOTICES/TOOLCHAIN/DOS32A.txt','HEADLESS.SH','HEADLESS.BAT','RT1715.CON','CLAIMS.JSON','TECHNICAL-SOURCES.TXT']:
            if name not in sums:raise ValueError('Missing release support file: '+name)
        provenance=json.loads((root/'PROVENANCE.JSON').read_text())
        env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy')
        start=time.monotonic()
        # Invoke the actual shipped wrapper from outside its own directory.
        # sh avoids ZIP extractors that discard executable permission bits.
        with (root/'host.log').open('w') as log:
            process=subprocess.Popen(['sh',str(root/'HEADLESS.SH')],cwd=root.parent,env=env,
                                     stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            try:code=process.wait(timeout=timeout)
            except BaseException:
                process.kill();process.wait();raise
        if code:raise ValueError('Release launcher failed: '+str(code))
        flight=(root/'FLIGHT.LOG').read_text();credits=(root/'CRED.LOG').read_text()
        if not credits.endswith('COMPLETE\n'):raise ValueError('Release did not complete credits')
        contract = root/'CHAPTERS.JSON'
        cues=verify_sync(flight,credits,contract if contract.exists() else None)
        schedule=verify_card_schedule(credits,(root/'CRED.CUE').read_text(),(root/'CRED.TIM').read_bytes())
        for name,expected in sums.items():
            if hashlib.sha256((root/name).read_bytes()).hexdigest()!=expected:
                raise ValueError('Playback modified packaged file: '+name)
        report={'passed':True,'archive_sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),
                'packaged_files':len(sums),'elapsed_seconds':round(time.monotonic()-start,2),
                'launcher':'sh HEADLESS.SH (unpacked, launched from parent directory)',
                'sync':cues,'schedule':schedule,'runtime_sha256':provenance['packaged_runtime_sha256']}
        if (root/'EXPAND.JSON').exists():
            from expansion_checks import verify as verify_effects
            expansion=json.loads((root/'EXPAND.JSON').read_text())
            report['expansion']={}
            for filename,key in [('FX.LOG','intro'),('POST.LOG','post')]:
                if expansion[key]:report['expansion'][key]=verify_effects((root/filename).read_text(),expansion[key])
        output.mkdir(parents=True,exist_ok=True)
        for name in ['host.log','FLIGHT.LOG','CRED.LOG']:(output/name).write_bytes((root/name).read_bytes())
        (output/'result.json').write_text(json.dumps(report,indent=2)+'\n')
        print('PASS: unpacked release, hashes, notices, headless launcher, all cues and clean exit')
        return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('archive',type=Path)
    p.add_argument('--output',type=Path,default=Path(__file__).parent/'build/release-verification')
    a=p.parse_args();verify(a.archive,a.output)
