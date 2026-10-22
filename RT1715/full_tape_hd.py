#!/usr/bin/env python3
"""Isolated 2x reflection-tape prototype; leaves the reviewed 1x build intact."""
import argparse,json,math,struct,subprocess
from pathlib import Path
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter,label
from build import ROOT,HERE
from full_water import tape_center

MESSAGE=b'THIS TAPE CANNOT PROVE WHAT IT SAYS'
TRACKS=(-12,-9,-6,0,3,6,9,12)

def texture():
    # Render at twice the native sample density, retaining physical dimensions.
    yy,xx=np.mgrid[:70,:800];x=xx/2;y=yy/2
    centers=np.array([tape_center(i/2) for i in range(800)])
    dy=y-centers
    light=np.rint(35+20*np.cos(dy/13*np.pi/2))
    pixels=np.where(np.abs(dy)<=14,192+light,0).astype(np.uint8)
    def hole(cx,cy,r):
        # True round coverage sampled at 2x, with softened edge pixels.
        for py in range(max(0,math.floor((cy-r)*2)-1),min(70,math.ceil((cy+r)*2)+2)):
            for px in range(max(0,math.floor((cx-r)*2)-1),min(800,math.ceil((cx+r)*2)+2)):
                coverage=sum(((px+(sx+.5)/4-.5)/2-cx)**2+((py+(sy+.5)/4-.5)/2-cy)**2<r*r for sy in range(4) for sx in range(4))/16
                if coverage>=.7:pixels[py,px]=0
                elif coverage>0 and pixels[py,px]>=192:pixels[py,px]=192+round((int(pixels[py,px])-192)*(1-coverage))
    for x in range(0,400,8):hole(x,tape_center(x)-3,.65)
    for i,value in enumerate(MESSAGE):
        x=24+i*8
        for bit,dy in enumerate(TRACKS):
            if value&(1<<bit):hole(x,tape_center(x)+dy,1.35)
    return pixels

def maps():
    groups=[];uv=np.zeros((200,320,2));mask=np.zeros((200,320),bool)
    for n in (1,2,3):
        data=(ROOT/f'WATER/WAT{n}.DAT').read_bytes();at=0;dest=[]
        for i in range(158*34):
            count=struct.unpack_from('<H',data,at)[0];at+=2
            addresses=struct.unpack_from(f'<{count}H',data,at);at+=count*2
            for address in addresses:
                y,x=divmod(address,320)
                uv[y,x]=(i%158,i//158);mask[y,x]=True;dest.append(address)
        if at!=len(data):raise ValueError('Unexpected tape UV table')
        groups.append((data,dest))
    # Original coordinates were rounded into large shared samples. Smooth only
    # within each disconnected projected surface to recover half-texel detail.
    components,count=label(mask);fine=np.zeros_like(uv)
    for component in range(1,count+1):
        region=components==component
        weight=gaussian_filter(region.astype(float),1.5)
        for axis in (0,1):
            field=gaussian_filter(uv[:,:,axis]*region,1.5)/np.maximum(weight,1e-12)
            fine[:,:,axis][region]=field[region]
    fine=np.rint(fine*2).astype(int);fine[:,:,0]=np.clip(fine[:,:,0],0,315);fine[:,:,1]=np.clip(fine[:,:,1],0,67)
    packed=[]
    for original,dest in groups:
        records=[struct.pack('<HHH',a,int(fine[a//320,a%320,0]),int(fine[a//320,a%320,1])*800) for a in dest]
        packed.append((original,struct.pack('<H',len(dest))+b''.join(records)))
    return packed

def build(released,output):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    pixels=texture();(output/'tape-800x70.bin').write_bytes(pixels.tobytes())
    subprocess.run(['nasm','-f','bin','-I',str(output)+'/',str(HERE/'full-scenes/tape-hd.asm'),'-o',str(output/'tape-hd.bin')],check=True)
    code=(output/'tape-hd.bin').read_bytes()
    if len(code)>65535:raise ValueError('HD texture/code segment overflow')
    raw=Path(released).read_bytes();data=bytearray(raw);h=struct.unpack_from('<14H',raw);oldbase=h[4]*16
    walker=bytes.fromhex('1e 8e d8 b8 00 a0 8e c0 8e e1 8e ea')
    clamp=bytes.fromhex('81 3e 8e 52 86 01 73 04 ff 06 8e 52')
    if raw.count(walker)!=1 or raw.count(clamp)!=1:raise ValueError('Released tape code anchors changed')
    patches=[(raw.index(walker),5,0,0xea),(raw.index(clamp),12,3,0x9a)]
    extra=max(0,(h[12]+4*(h[3]+2)-oldbase+15)//16)*16
    data[oldbase:oldbase]=bytes(extra);base=oldbase+extra
    struct.pack_into('<H',data,8,base//16)
    data.extend(bytes(h[5]*16));data.extend(bytes((-len(data))%16))
    code_segment=(len(data)-base)//16;data.extend(code);data.extend(bytes((-len(data))%16))
    for n,(at,length,offset,opcode) in enumerate(patches):
        at+=extra;data[at:at+length]=bytes([opcode])+struct.pack('<HH',offset,code_segment)+b'\x90'*(length-5)
        site=at+3-base;struct.pack_into('<HH',data,h[12]+4*(h[3]+n),site%16,site//16)
    sizes=[]
    for original,table in maps():
        oldoff=raw.index(original);oldseg=(oldoff-oldbase)//16;newseg=(len(data)-base)//16
        if len(table)>65535:raise ValueError('HD map overflow')
        refs=0
        for i in range(h[3]):
            off,seg=struct.unpack_from('<HH',data,h[12]+4*i);at=base+seg*16+off
            if struct.unpack_from('<H',data,at)[0]==oldseg:struct.pack_into('<H',data,at,newseg);refs+=1
        if refs!=1:raise ValueError('Tape map relocation count changed')
        data.extend(table);data.extend(bytes((-len(data))%16));sizes.append(len(table))
    old=(ROOT/'WATER/MIEKKA.SCI').read_bytes();at=data.index(old)
    for i in range(64):data[at+10+(192+i)*3:at+13+(192+i)*3]=bytes((i,min(63,round(i*.88)),min(63,round(i*.59))))
    struct.pack_into('<H',data,6,h[3]+2);struct.pack_into('<HH',data,2,len(data)%512,(len(data)+511)//512);struct.pack_into('<H',data,18,0)
    (output/'RAYSCRL.EXE').write_bytes(data)
    preview=Image.fromarray(pixels).convert('P');preview.putpalette([v*4 for v in data[at+10:at+778]]);preview.save(output/'tape-2x.png')
    (output/'prototype.json').write_text(json.dumps({'texture':[800,70],'screen':[320,200],'texture_bytes':pixels.size,'map_bytes':sizes,'exe_bytes':len(data),'original_exe_bytes':len(raw),'sampling':'half-texel UVs reconstructed within disconnected projected surfaces','message':MESSAGE.decode(),'review_status':'experimental; not installed in full runtime'},indent=2)+'\n')
    return output/'RAYSCRL.EXE'

if __name__=='__main__':
    from full_build import unpack
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=HERE/'build/tape-hd/assets');a=p.parse_args();print(build(unpack('RAYSCRL.EXE'),a.output))
