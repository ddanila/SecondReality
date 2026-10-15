#!/usr/bin/env python3
"""Host-build protected-mode native tests; execute only tests inside DOSBox-X."""
import ctypes
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import build


def raster_fixtures(out):
    # The portable host backend uses wide host arithmetic and a scalar pixel
    # loop. Compare complete images, including clipping, untouched pixels and
    # interpolated gradients, against the actual 32-bit DOS implementation.
    source=(build.HERE/'depth.c').read_text()
    source+="""
unsigned host_hash(void) {
    unsigned h=2166136261U;int i;
    for(i=0;i<64000;i++) { h=(h^test_depth[i])*16777619U;h=(h^test_color[i])*16777619U; }
    return h;
}
"""
    (out/'reference.c').write_text(source)
    subprocess.run(['cc','-shared','-fPIC','-O2','-DRT_HOST_TEST','-I'+str(build.HERE),str(out/'reference.c'),'-o',str(out/'reference.so')],check=True)
    lib=ctypes.CDLL(str(out/'reference.so'))
    class Vertex(ctypes.Structure):
        _fields_=[(name,ctypes.c_long) for name in ('x','y','z','c')]
    lib.rt_raster.argtypes=[ctypes.POINTER(Vertex),ctypes.c_int,ctypes.c_int]
    lib.host_hash.restype=ctypes.c_uint
    lib.rt_depth_window(0,320,25,175)
    rng=random.Random(1716);rows=[]
    for i in range(160):
        color=rng.randrange(256)
        vertices=[(rng.randrange(-200,521),rng.randrange(-120,321),rng.randrange(1,65536) if i%3==0 else rng.randrange(500,6000),
                   rng.randrange(256) if i%2 else color) for _ in range(3)]
        lib.rt_depth_begin();lib.rt_raster((Vertex*3)(*(Vertex(*v) for v in vertices)),3,i&1)
        rows.append('{ {'+','.join('{'+','.join(map(str,v))+'}' for v in vertices)+'},'+str(i&1)+','+str(lib.host_hash())+'UL}')
    (out/'pm_raster_cases.h').write_text('static struct { rt_vertex v[3];int decal;unsigned long hash; } raster_cases[]={'+',\n'.join(rows)+'};\n')

def main():
    out=build.HERE/'build/pm-tests';out.mkdir(exist_ok=True)
    source=build.HERE/'build/renderer32'
    watcom=Path(os.environ.get('WATCOM32',build.HERE/'build/toolchain/watcom'))
    cc=next(p for p in (watcom/'armo64/wcc386',watcom/'binl64/wcc386') if p.exists())
    rng=random.Random(1715);cases=[]
    while len(cases)<2000:
        a=rng.randint(-2147483648,2147483647);b=rng.randint(-2147483648,2147483647)
        d=rng.randint(1,2147483647)*rng.choice((-1,1))
        q=abs(a*b)//abs(d)*(-1 if (a*b<0)!=(d<0) else 1)
        if -2147483648<=q<=2147483647:cases.append((a,b,d,q))
    (out/'pm_vectors.h').write_text('static const long vectors[][4]={'+','.join('{'+','.join(str(v)+'L' for v in row)+'}' for row in cases)+'};\n')
    shutil.copyfile(build.HERE/"depth.h",out/"depth.h")
    raster_fixtures(out)
    for name in ('pm.h','pm_fast.h','pm_platform.c','pm_fast.asm','depth.h','depth.c','pm_tangent.h'):
        shutil.copyfile(source/name,out/name)
    shutil.copyfile(build.HERE/'pm_test.c',out/'pm_test.c')
    # Use current shared raster source, not a stale build copy.
    shutil.copyfile(build.HERE/'depth.c',out/'depth.c')
    for name in ('pm_test','pm_platform','depth'):
        subprocess.run([str(cc),'-zq','-bt=dos','-mf','-3r','-ot','-s','-ecc','-dRT_PM','-dRT_PM_VERIFY',f'-i={watcom / "h"}',f'-fo={name}.obj',name+'.c'],cwd=out,check=True)
    subprocess.run([build.tool('jwasm'),'-q','-Cp','-omf','-Fopm_fast.obj','pm_fast.asm'],cwd=out,check=True)
    subprocess.run([build.tool('wlink'),'format','os2','le','option','quiet','option','stack=65536',
        'option',f'stub={watcom / "binw/dos32a.exe"}','name','TEST.EXE','file','pm_test.obj',
        'file','pm_platform.obj','file','depth.obj','file','pm_fast.obj','libpath',str(watcom/'lib386/dos'),
        'libpath',str(watcom/'lib386')],cwd=out,check=True)
    (out/'RESULT.TXT').unlink(missing_ok=True)
    (out/'TEST.BAT').write_bytes(b'@echo off\r\nTEST.EXE > TEST.LOG\r\nif errorlevel 1 goto fail\r\necho PASS > RESULT.TXT\r\ngoto done\r\n:fail\r\necho FAIL > RESULT.TXT\r\n:done\r\nexit\r\n')
    command=[build.tool('dosbox-x'),'-conf',str(build.HERE/'dosbox-x.conf'),'-noautoexec','-fastlaunch',
             '-set','cpu cycles=fixed 300000','-c',f'mount c "{out}"','-c','c:','-c','test.bat']
    with (out/'dosbox.log').open('w') as log:
        p=subprocess.Popen(command,env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),
                           stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:p.wait(timeout=60)
        except BaseException:p.kill();p.wait();raise
    text=(out/'TEST.LOG').read_text();print(text)
    if p.returncode or not (out/'RESULT.TXT').exists() or (out/'RESULT.TXT').read_text().strip()!='PASS':
        raise SystemExit('Protected-mode kernel tests failed; inspect build/pm-tests')
    (out/'result.json').write_text(json.dumps({'passed':True,'headless':True,'cycles':'fixed 300000','log':text},indent=2)+'\n')

if __name__=='__main__':main()
