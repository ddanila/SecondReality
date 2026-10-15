#!/usr/bin/env python3
"""Capture real TOS/M startup masks from DAC's read-only historical media.

Optional asset-authoring tool; regular DOS builds use the checked-in masks.
Requires Node and the host Python environment. Does not modify DAC or its disk.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent
SAMPLES={'loader':12,'system':38,'startup':56,'prompt':100}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dac',type=Path,default=HERE.parent.parent/'dac')
    parser.add_argument('--output',type=Path,default=HERE/'assets/robotron/boot')
    args=parser.parse_args();dac=args.dac.resolve();out=args.output.resolve()
    manifest=json.loads((dac/'public/emulator/manifest.json').read_text())
    media=json.loads((dac/'src/robotron-media.json').read_text())
    for entry in media['files']:
        data=(dac/'public/media/robotron'/entry['file']).read_bytes()
        if hashlib.sha256(data).hexdigest()!=entry['sha256']:
            raise ValueError('DAC media hash mismatch: '+entry['file'])
    for name in ('dac.js','dac.wasm'):
        if hashlib.sha256((dac/'public/emulator'/name).read_bytes()).hexdigest()!=manifest['sha256'][name]:
            raise ValueError('DAC emulator hash mismatch: '+name)
    with tempfile.TemporaryDirectory(prefix='rt1715-boot-') as temp:
        work=Path(temp)
        script=f'''import {{readFile,writeFile}} from 'node:fs/promises';
import create from {json.dumps((dac/'public/emulator/dac.js').as_uri())};
const root={json.dumps(str(dac))},out={json.dumps(temp)};
const w=await create({{wasmBinary:await readFile(root+'/public/emulator/dac.wasm')}});
const s=w._dac_create(2);
for(const [slot,name] of [[0,'s550.bin'],[1,'cas.bin'],[3,'tosm10.img']]){{
 const b=await readFile(root+'/public/media/robotron/'+name),p=w._malloc(b.length);
 w.HEAPU8.set(b,p);
 if((slot===3?w._dac_mount(s,p,b.length,0):w._dac_load(s,slot,p,b.length))!==0)throw Error(name);
 w._free(p);
}}
w._dac_power(s,1);
for(let n=1;n<=100;n++){{
 for(let k=0;k<10;k++)if(w._dac_run(s,100000)!==100000)throw Error('short run');
 if({json.dumps(list(SAMPLES.values()))}.includes(n)){{
  const p=w._dac_video(s);
  await writeFile(out+'/'+n+'.rgba',w.HEAPU8.slice(p,p+640*288*4));
 }}
}}
w._dac_destroy(s);
'''
        (work/'capture.mjs').write_text(script)
        subprocess.run(['node',str(work/'capture.mjs')],check=True,timeout=90)
        out.mkdir(parents=True,exist_ok=True)
        for name,clocks in SAMPLES.items():
            data=(work/f'{clocks}.rgba').read_bytes()
            rgba=np.array(Image.frombytes('RGBA',(640,288),data))
            bitmap=Image.fromarray(rgba[:,:,1]>100)
            if name=='prompt':
                cursor=Image.new('1',bitmap.size)
                cursor.paste(bitmap.crop((16,48,24,60)),(16,48));cursor.save(out/'cursor.png')
                bitmap.paste(0,(16,48,24,60))
            bitmap.save(out/(name+'.png'))
    provenance={'description':'Unmodified DAC S550 + TOS/M 1.0 read-only cold boot; foreground masks from actual 640x288 framebuffer. Final cursor separated for blinking. Timing compressed for demo.',
                'emulator':manifest,'media':media,'samples_million_clocks':SAMPLES,
                'foreground':'green channel > 100','cursor_box':[16,48,24,60],
                'assets':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.glob('*.png'))}}
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    print('Captured real TOS/M boot:',out)


if __name__=='__main__':main()
