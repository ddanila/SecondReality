#!/usr/bin/env python3
"""Host-build and test real-mode assembly kernels in isolated headless DOSBox-X."""
import json
import os
from pathlib import Path
import random
import shutil
import subprocess
import build

def main():
    out=build.HERE/'build/native-tests';out.mkdir(exist_ok=True)
    cc=build.tool('wcc');watcom=Path(cc).parents[2]
    cases=[(a,b,d) for a,b,d in [(0,1,1),(2147483647,2147483647,2147483647),
           (-2147483648,1,1),(-2147483648,-1,2),(33553920,64,512),
           (1234567,-7654321,9000000),(1,1,-3),(-1,1,3)]]
    rng=random.Random(1715)
    while len(cases)<2000:
        a=rng.randint(-2147483648,2147483647);b=rng.randint(-2147483648,2147483647)
        d=rng.randint(1,2147483647)*rng.choice((-1,1))
        if abs(a*b)//abs(d)<=2147483647:cases.append((a,b,d))
    def literal(n):return '(-2147483647L-1)' if n==-2147483648 else f'{n}L'
    rows=[]
    for a,b,d in cases:
        q=(abs(a*b)//abs(d))*(-1 if (a*b<0)!=(d<0) else 1)
        rows.append('{'+','.join(map(literal,(a,b,d,q)))+'}')
    # 32KB vectors live outside DGROUP, leaving room for reference buffers.
    (out/'vectors.h').write_text('static const long __far vectors[][4]={\n'+',\n'.join(rows)+'\n};\n')
    for name in ('fast.asm','fast.h','fast_test.c','lighting.h'):shutil.copyfile(build.HERE/name,out/name)
    subprocess.run([build.tool('jwasm'),'-q','-Cp','-omf','-FoFAST.OBJ','fast.asm'],cwd=out,check=True)
    subprocess.run([cc,'-zq','-bt=dos','-ml','-3','-ot','-s','-ecc',f'-i={watcom / "h"}',
                    '-fo=TEST.OBJ','fast_test.c'],cwd=out,check=True)
    subprocess.run([build.tool('wlink'),'format','dos','option','quiet','option','stack=8192',
                    'option','map=TEST.MAP','name','TEST.EXE','file','TEST.OBJ','file','FAST.OBJ',
                    'libpath',str(watcom/'lib286/dos'),'library','clibl'],cwd=out,check=True)
    (out/'RESULT.TXT').unlink(missing_ok=True)
    (out/'TEST.BAT').write_bytes(b'@echo off\r\nTEST.EXE > TEST.LOG\r\nif errorlevel 1 goto fail\r\necho PASS > RESULT.TXT\r\ngoto done\r\n:fail\r\necho FAIL > RESULT.TXT\r\n:done\r\nexit\r\n')
    command=[build.tool('dosbox-x'),'-conf',str(build.HERE/'dosbox-x.conf'),'-noautoexec','-fastlaunch',
             '-set','cpu cycles=fixed 300000','-c',f'mount c "{out}"','-c','c:','-c','test.bat']
    with (out/'dosbox.log').open('w') as log:
        p=subprocess.Popen(command,env=dict(os.environ,SDL_VIDEODRIVER='dummy',SDL_AUDIODRIVER='dummy'),
                           stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
        try:p.wait(timeout=90)
        except BaseException:p.kill();p.wait();raise
    text=(out/'TEST.LOG').read_text();print(text)
    if p.returncode or not (out/'RESULT.TXT').exists() or (out/'RESULT.TXT').read_text().strip()!='PASS':
        raise SystemExit('Native kernel tests failed; inspect build/native-tests')
    (out/'result.json').write_text(json.dumps({'passed':True,'headless':True,'cycles':'fixed 300000','log':text},indent=2)+'\n')

if __name__=='__main__':main()
