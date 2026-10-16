"""Bake visible source-triangle IDs, not pixels; DOS still projects and draws."""
import argparse, os, struct, subprocess, tempfile
from pathlib import Path

HERE=Path(__file__).resolve().parent

def bake(dos,output):
    import concurrent.futures
    # Exact normalized poses shared with effects.c; no temporal guess at visibility.
    scenes=[(3,14.770),(10,3.692),(11,7.384)]
    with tempfile.TemporaryDirectory(prefix='rt-fx-vis-') as temp:
        temp=Path(temp);exe=temp/'renderer'
        subprocess.run(['cc','-O2','-DFX_HOST',str(HERE/'effects.c'),'-o',str(exe),'-lm'],check=True)
        jobs=[]
        for scene,length in scenes:
            count=round(length*25)+1
            for i in range(count):jobs.append((scene,length,count,i))
        def frame(job):
            scene,length,count,i=job;path=temp/f'{scene}-{i}'
            env=dict(os.environ,FX_VIS_WRITE=str(path),FX_VIS_BAKE='1')
            subprocess.run([str(exe),str(scene),str(length*i/(count-1)),str(length),os.devnull],cwd=dos,env=env,check=True)
            return path.read_bytes()
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:payload=list(pool.map(frame,jobs))
        ids=sorted({v for record in payload for v in struct.unpack('<'+str((len(record)-4)//4)+'I',record[4:])})
        if len(ids)>65535:raise ValueError('Visible triangle budget exceeded')
        remap={old:new for new,old in enumerate(ids)}
        raw=(dos/'FX.MSH').read_bytes();n=struct.unpack_from('<I',raw)[0]
        (output.parent/'FX.DRW').write_bytes(struct.pack('<I',len(ids))+raw[4:28]+b''.join(raw[28+i*20:48+i*20] for i in ids)+raw[28+n*20:])
        data=bytearray(struct.pack('<4sI',b'FV02',len(scenes)));offset=0
        for scene,length in scenes:
            count=round(length*25)+1;data+=struct.pack('<II',scene,count)
            for record in payload[offset:offset+count]:
                old=struct.unpack('<'+str((len(record)-4)//4)+'I',record[4:])
                data+=struct.pack('<I',len(old))+struct.pack('<'+str(len(old))+'H',*(remap[v] for v in old))
            offset+=count
        output.write_bytes(data)
    print(output,len(data),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('dos',type=Path);p.add_argument('output',type=Path);a=p.parse_args();bake(a.dos.resolve(),a.output.resolve())
