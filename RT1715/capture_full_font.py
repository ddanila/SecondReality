"""Extract the TOS/M-loaded character RAM from the verified DAC emulator."""
import hashlib,json,subprocess,tempfile
from pathlib import Path
from build import HERE,ROOT


def capture():
    dac=ROOT.parent/'dac';manifest=json.loads((dac/'src/robotron-media.json').read_text())
    for name in ('s550.bin','cas.bin','tosm10.img'):
        record=next(r for r in manifest['files'] if r['file']==name)
        if hashlib.sha256((dac/'public/media/robotron'/name).read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Media hash mismatch')
    out=HERE/'assets/full-demo/dots';out.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as temp:
        work=Path(temp)
        script=f'''import {{readFile,writeFile}} from 'node:fs/promises';
import create from {json.dumps((dac/'public/emulator/dac.js').as_uri())};
const root={json.dumps(str(dac))};
const w=await create({{wasmBinary:await readFile(root+'/public/emulator/dac.wasm')}}),s=w._dac_create(2);
for(const [slot,name] of [[0,'s550.bin'],[1,'cas.bin'],[3,'tosm10.img']]){{
const b=await readFile(root+'/public/media/robotron/'+name),p=w._malloc(b.length);w.HEAPU8.set(b,p);
if((slot===3?w._dac_mount(s,p,b.length,0):w._dac_load(s,slot,p,b.length))!==0)throw Error(name);w._free(p);
}}
w._dac_power(s,1);for(let i=0;i<1000;i++)if(w._dac_run(s,100000)!==100000)throw Error('short run');
const n=w._dac_state_size(s),p=w._malloc(n);if(w._dac_state_save(s,p,n)!==0)throw Error('state save');
await writeFile({json.dumps(str(work/'state.bin'))},w.HEAPU8.slice(p,p+n));w._free(p);w._dac_destroy(s);
'''
        (work/'extract.mjs').write_text(script);subprocess.run(['node',str(work/'extract.mjs')],check=True,timeout=90)
        state=(work/'state.bin').read_bytes();rom=(dac/'public/media/robotron/s550.bin').read_bytes();at=state.find(rom)
        if at<0 or state.find(rom,at+1)>=0:raise ValueError('Unique ROM anchor missing')
        font=state[at+2048:at+2048+4096]
        if len(font)!=4096 or not any(font):raise ValueError('Character RAM missing')
    (out/'tosm-chargen.bin').write_bytes(font)
    (out/'font-provenance.json').write_text(json.dumps({'source':manifest['source'],'description':'TOS/M 1.0 character RAM after 100 million clocks; rows addressed as y*128+character','media':manifest['files'],'font_sha256':hashlib.sha256(font).hexdigest(),'wasm_sha256':hashlib.sha256((dac/'public/emulator/dac.wasm').read_bytes()).hexdigest(),'rights':manifest['rights']},indent=2)+'\n')
    return out

if __name__=='__main__':print(capture())
