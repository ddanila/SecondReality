"""Host-build the 32-bit renderer with Open Watcom and embedded DOS/32A."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from build import HERE, ROOT, tool, masm_source
from music import flight_header


def build_renderer(build, assembler=None, linker=None, watcom=None):
    watcom=Path(watcom or os.environ.get('WATCOM32',build/'toolchain/watcom')).resolve()
    candidates=[watcom/'armo64/wcc386',watcom/'binl64/wcc386',watcom/'binl/wcc386']
    compiler=next((p for p in candidates if p.is_file()),None)
    if compiler is None:
        raise SystemExit('Set WATCOM32 to a native Open Watcom installation with wcc386, h/, lib386/ and binw/dos32a.exe')
    assembler=assembler or tool('jwasm');linker=linker or tool('wlink')
    out=build/'renderer32';out.mkdir(parents=True,exist_ok=True)
    (out/'MUSIC.H').write_text(flight_header(ROOT/'MAIN/MUSIC0.S3M'))
    table=(ROOT/'VISU/AVISTAN.INC').read_text(encoding='cp437')
    values=[int(n) for row in table.splitlines() if row.startswith('dw ') for n in re.findall(r'\d+',row)]
    assert len(values)==256
    (out/'pm_tangent.h').write_text('static const unsigned short rt_tangent[256]={'+','.join(map(str,values))+'};\n')
    from bake import signature
    (out/'bake_signature.h').write_text('#define RT_BAKE_SIGNATURE '+str(signature())+'UL\n')
    for name in ('bake_codec.h','baked.c','baked.h','pm.h','pm_fast.h','pm_fast.asm','pm_platform.c','pm_main.c','painter.c','depth.c','depth.h','detail_aa.h','lighting.h'):
        shutil.copyfile(HERE/name,out/name)
    for name in ('pm_main','pm_platform','painter','depth','baked'):
        subprocess.run([str(compiler),'-zq','-bt=dos','-mf','-3r','-ot','-s','-ecc','-dRT_PM',
                        f'-i={watcom / "h"}',f'-fo={name}.obj',name+'.c'],cwd=out,check=True)
    subprocess.run([assembler,'-q','-Cp','-omf','-Fopm_fast.obj','pm_fast.asm'],cwd=out,check=True)
    cmd=[linker,'format','os2','le','option','quiet','option','stack=65536',
         'option',f'stub={watcom / "binw/dos32a.exe"}','option','map=U2E.MAP',
         'name',str(build/'dos/U2E.EXE')]
    for name in ('pm_main','pm_platform','painter','depth','baked','pm_fast'):cmd+=['file',name+'.obj']
    cmd+=['libpath',str(watcom/'lib386/dos'),'libpath',str(watcom/'lib386')]
    subprocess.run(cmd,cwd=out,check=True)
    (out/'toolchain.json').write_text(json.dumps({str(p.relative_to(watcom)):hashlib.sha256(p.read_bytes()).hexdigest()
        for p in (compiler,watcom/'binw/dos32a.exe',watcom/'lib386/dos/clib3r.lib')},indent=2)+'\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--watcom-root',type=Path)
    args=parser.parse_args();build=HERE/'build'
    build_renderer(build,watcom=args.watcom_root)
    # Rebuild the resident launcher with the frame-boundary DPMI bridge.
    (build/'RT1715.ASM').write_text(masm_source(True,True),encoding='cp437')
    subprocess.run([tool('jwasm'),'-q','-Cp','-omf','-FoRT1715.OBJ','RT1715.ASM'],cwd=build,check=True)
    subprocess.run([tool('wlink'),'format','dos','option','quiet','option','map=RT1715.MAP',
                    'name','dos/RT1715.EXE','file','RT1715.OBJ','file','STMIK.OBJ'],cwd=build,check=True)
    from bake import signature,bake
    import struct
    cache=build/'dos/U2E.BKC';route=build/'dos/U2E.VIS'
    if route.exists():
        with cache.open('rb') if cache.exists() else open(os.devnull,'rb') as f:header=f.read(24)
        expected=struct.unpack_from('<I',route.read_bytes(),4)[0]
        if len(header)!=24 or header[:4]!=b'BKC1' or struct.unpack_from('<II',header,4)!=(signature(),expected):
            bake(build/'dos')
    manifest=json.loads((build/'assets.json').read_text())
    if cache.exists():
        manifest=[entry for entry in manifest if entry['file']!='U2E.BKC']
        manifest.append({'file':'U2E.BKC','source':'Native host drawing bake (RT1715/bake.py)',
                         'sha256':hashlib.sha256(cache.read_bytes()).hexdigest()})
    for entry in manifest:
        if entry['file']=='U2E.EXE':
            entry['source']='Host-built 32-bit renderer (RT1715/pm_renderer.py)'
            entry['sha256']=hashlib.sha256((build/'dos/U2E.EXE').read_bytes()).hexdigest()
    (build/'assets.json').write_text(json.dumps(manifest,indent=2)+'\n')

if __name__=='__main__':main()
