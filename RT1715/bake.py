"""Bake filtered markings and visible projected faces on the native host CPU."""
import argparse,ctypes,ctypes.util,hashlib,json,struct,subprocess,time,zlib
from pathlib import Path
import animation,scene,route_cache
HERE=Path(__file__).resolve().parent

def library(build):
    flags=['cc','-O2','-fPIC','-DRT_HOST_TEST','-DRT_BAKE']
    subprocess.run(flags+['-c',str(HERE/'depth.c'),'-o',str(build/'bake-depth.o')],check=True)
    subprocess.run(flags+['-DRT_PM','-D__cdecl=','-c',str(HERE/'bake_host.c'),'-o',str(build/'bake-host.o')],check=True)
    subprocess.run(['cc','-shared',str(build/'bake-depth.o'),str(build/'bake-host.o'),'-o',str(build/'bake-host.so')],check=True)
    lib=ctypes.CDLL(str(build/'bake-host.so'))
    lib.bake_load.argtypes=[ctypes.c_uint,ctypes.c_char_p,ctypes.c_uint]
    lib.bake_begin.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_int,ctypes.c_char_p]
    lib.bake_object.argtypes=[ctypes.c_uint,ctypes.POINTER(ctypes.c_long)]
    lib.bake_export.argtypes=lib.bake_image.argtypes=[ctypes.c_char_p]
    lib.rt_detail_init.argtypes=[ctypes.c_char_p,ctypes.c_char_p]
    return lib

def signature():
    names=('bake.py','bake_host.c','painter.c','lighting.h','depth.c','detail_aa.h','pm_platform.c','pm_fast.asm')
    return zlib.crc32(b''.join((HERE/n).read_bytes() for n in names))


def compressor():
    name=ctypes.util.find_library('lz4')
    if not name:
        name=next((str(p) for p in (Path('/opt/homebrew/opt/lz4/lib/liblz4.dylib'),Path('/usr/local/opt/lz4/lib/liblz4.dylib')) if p.exists()),None)
    if not name:raise RuntimeError('Host bake needs liblz4 (brew install lz4 or liblz4-dev)')
    lib=ctypes.CDLL(name);lib.LZ4_compress_default.argtypes=[ctypes.c_char_p,ctypes.c_void_p,ctypes.c_int,ctypes.c_int]
    def compress(raw):
        buffer=ctypes.create_string_buffer(len(raw)+len(raw)//255+32)
        n=lib.LZ4_compress_default(raw,buffer,len(raw),len(buffer))
        if not n:raise ValueError('LZ4 compression failed')
        return buffer.raw[:n]
    return compress


def pack_frame(stem):
    raw=stem.with_suffix('.mask').read_bytes()
    wanted=set(struct.unpack_from('<64000I',raw));wanted.discard(0);groups={}
    for p,j,col,z,alpha,unused,tag in struct.iter_unpack('<HBBHBBI',raw[256000:]):
        wanted.add(tag);key=(p,z,col,alpha);groups[key]=groups.get(key,0)|(1<<j)
    commands=[];raw=stem.with_suffix('.cmd').read_bytes();pos=0;submitted=0
    while pos<len(raw):
        tag,n,decal=struct.unpack_from('<III',raw,pos);pos+=12
        vertices=list(struct.iter_unpack('<iiii',raw[pos:pos+16*n]));pos+=16*n;submitted+=1
        if tag in wanted:
            commands.append(bytes([n,decal])+b''.join(struct.pack('<hhHB',*v) for v in vertices))
    masks=b''.join(struct.pack('<HHHBB',p,mask,z,col,alpha) for (p,z,col,alpha),mask in sorted(groups.items()))
    faces=b''.join(struct.pack('<I',tag) for tag in sorted(wanted))
    data=struct.pack('<III',len(wanted),len(commands),len(groups))+faces+b''.join(commands)+masks
    return data,{'submitted':submitted,'retained':len(commands),'mask_groups':len(groups)}

def bake(dos,poses=None,lod_experiment=False):
    build=dos.parent;out=build/'baked';out.mkdir(exist_ok=True)
    lib=library(build);materials=(dos/'U2E.00M').read_bytes();mapping=animation.mapping(materials)
    palette=bytearray(materials[16:784]);palette[252*3:]=bytes(12)
    palette=bytes(palette);lookup=(dos/'U2E.AA').read_bytes();lib.rt_detail_init(palette,lookup)
    for i,slot in enumerate(mapping[1:],1):
        raw=(dos/f'U2E.{slot:03}').read_bytes();lib.bake_load(i,raw,len(raw))
    route=(dos/'U2E.VIS').read_bytes();count=struct.unpack_from('<I',route,8)[0]
    offsets=struct.unpack_from(f'<{count+1}I',route,16);indices=route[20+count*4:]
    frames=animation.decode((dos/'U2E.0AB').read_bytes(),len(mapping));states=[[0]*12 for _ in mapping]
    source=(HERE.parent/'VISU/AVISTAN.INC').read_text(encoding='cp437')
    import re
    tangent=[int(n) for row in source.splitlines() if row.startswith('dw ') for n in re.findall(r'\d+',row)]
    results=[];start=time.monotonic();compress=compressor();packed=[];sizes=[];checks=[]
    header_size=24+4*(count+1)+8*count
    output=(out/'lod-trial.tmp' if lod_experiment else dos/'.U2E.BKC.tmp').open('wb');output.write(bytes(header_size));file_offsets=[0]
    maximum=0
    for row,(records,fov) in enumerate(frames):
        for record in records:states[record['object']]=record['state']
        frame=(row+1)*2
        if poses and frame not in poses:
            file_offsets.append(file_offsets[-1]);sizes.append(0);checks.append(0);continue
        half=max(512,min(16383,fov*128));px=160*tangent[half>>6]>>8;py=px*225>>8
        stem=out/f'{frame:04}'
        lib.bake_begin(frame,px,py,str(stem.with_suffix('.cmd')).encode())
        for i in indices[offsets[row]:offsets[row+1]]:
            state=(ctypes.c_long*12)(*route_cache.compose(states[0],states[i]))
            lib.bake_object(i,state)
        lib.bake_end();lib.bake_export(str(stem.with_suffix('.mask')).encode());lib.bake_image(str(stem.with_suffix('.raw')).encode())
        raw=stem.with_suffix('.raw').read_bytes();planar=b''.join(raw[p::4] for p in range(4))
        payload,stats=pack_frame(stem)
        if lod_experiment:
            baseline=raw;old_stats=stats
            ctypes.c_int.in_dll(lib,'bake_mesh_lod').value=1
            lib.bake_begin(frame,px,py,str(stem.with_suffix('.cmd')).encode())
            for i in indices[offsets[row]:offsets[row+1]]:
                lib.bake_object(i,(ctypes.c_long*12)(*route_cache.compose(states[0],states[i])))
            lib.bake_end();lib.bake_export(str(stem.with_suffix('.mask')).encode());lib.bake_image(str(stem.with_suffix('.raw')).encode())
            ctypes.c_int.in_dll(lib,'bake_mesh_lod').value=0
            candidate=stem.with_suffix('.raw').read_bytes();payload,stats=pack_frame(stem)
            stats.update(original_retained=old_stats['retained'],changed_pixels=sum(a!=b for a,b in zip(baseline,candidate)))
        compressed=compress(payload)
        output.write(compressed);file_offsets.append(file_offsets[-1]+len(compressed));sizes.append(len(payload));checks.append(route_cache.fnv(payload))
        maximum=max(maximum,len(payload))
        rgb=b''.join(bytes(palette[c*3+k]*255//63 for k in range(3)) for c in raw)
        image_hash=hashlib.sha256(b'P6\n320 200\n255\n'+rgb).hexdigest()
        results.append({'frame':frame,'color':f'{route_cache.fnv(planar):08x}','ppm_sha256':image_hash,**stats,'raw_bytes':len(payload),'bytes':len(compressed)})
        for ext in ('.mask','.cmd','.raw'):stem.with_suffix(ext).unlink()
        if len(results)%100==0:print(frame,round(time.monotonic()-start,1),'seconds',flush=True)
    output.seek(0);output.write(struct.pack('<4sIIIII',b'BKC1',signature(),struct.unpack_from('<I',route,4)[0],count,len(mapping),maximum))
    output.write(struct.pack(f'<{len(file_offsets)}I',*file_offsets));output.write(struct.pack(f'<{len(sizes)}I',*sizes));output.write(struct.pack(f'<{len(checks)}I',*checks));output.close()
    if lod_experiment:(out/'lod-trial.tmp').unlink()
    else:(dos/'.U2E.BKC.tmp').replace(dos/'U2E.BKC')
    (out/('lod-trial.json' if lod_experiment else 'result.json')).write_text(json.dumps(results,indent=2)+'\n')
    return results

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--dos-dir',type=Path,default=HERE/'build/dos');p.add_argument('--poses',nargs='+',type=int);p.add_argument('--lod-experiment',action='store_true')
    a=p.parse_args();r=bake(a.dos_dir,a.poses,a.lod_experiment);print('Baked',len(r),'poses;',sum(x['bytes'] for x in r),'compressed bytes')
