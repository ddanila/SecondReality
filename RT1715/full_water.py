"""Replace water-scene assets and shade mapping while retaining original cues."""
import json, math, struct, subprocess
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from build import HERE,ROOT


def replace_once(exe,old,new):
    if len(old)!=len(new) or exe.count(old)!=1:
        raise ValueError('Asset size or unique released-asset match changed')
    return exe.replace(old,new,1)


def tape_masks(draft):
    """Shared silhouette for occlusion and a readable displaced cast shadow."""
    from scipy.ndimage import shift
    rgb=np.asarray(draft,dtype=float)
    tape=(rgb[:,:,0]>rgb[:,:,2]*1.08)&(rgb[:,:,1]>rgb[:,:,2]*1.03)&(rgb[:,:,0]>35)
    shadow=shift(tape.astype(np.uint8),(9,-18),order=0,mode='constant').astype(bool)&~tape
    return tape,shadow


def water_projection(exe,draft,output):
    """Rebuild the baked leaf occlusion using the replacement tape silhouette.

    Keep the released 237x31 UV domain. Extended tables live
    after the original load image AND its reserved BSS/stack, with relocated
    segment references; no original code/data addresses or cues move.
    """
    from scipy.interpolate import griddata
    from scipy.spatial import ConvexHull
    from scipy.ndimage import shift
    points=[];uv=[];tables=[]
    for n in (1,2,3):
        old=(ROOT/f'FOREST/POS{n}.DAT').read_bytes();tables.append(old);at=0
        for i in range(237*31):
            count=struct.unpack_from('<H',old,at)[0];at+=2
            for address in struct.unpack_from(f'<{count}H',old,at):
                points.append((address%320,address//320));uv.append((i%237,i//237))
            at+=count*2
        if at!=len(old):raise ValueError('Unexpected released water map')
    points=np.array(points);uv=np.array(uv)
    area=Image.new('L',(320,200));hull=ConvexHull(points)
    ImageDraw.Draw(area).polygon([tuple(p) for p in points[hull.vertices]],fill=255)
    tape,shadow=tape_masks(draft)
    # Shadowed water remains projected: its separate palette bank dims both
    # the water and the passing letters. Only solid tape blocks the projector.
    domain=np.asarray(area).astype(bool)&~tape
    yy,xx=np.where(domain);dest=np.c_[xx,yy]
    field=griddata(points,uv,dest,method='linear')
    bad=np.any(~np.isfinite(field),axis=1)
    field[bad]=griddata(points,uv,dest[bad],method='nearest')
    coords=np.rint(field).astype(int);coords[:,0]=np.clip(coords[:,0],0,236);coords[:,1]=np.clip(coords[:,1],0,30)
    groups=coords[:,1]*237+coords[:,0]
    data=bytearray(exe);header=struct.unpack_from('<14H',data);base=header[4]*16
    reserved_end=len(data)+header[5]*16
    data.extend(bytes((-len(data))%16))
    data.extend(bytes(max(0,reserved_end-len(data))))
    data.extend(bytes((-len(data))%16))
    reports=[]
    for n,old in enumerate(tables):
        oldoff=exe.find(old)
        if oldoff<0 or exe.count(old)!=1 or (oldoff-base)%16:raise ValueError('Water table segment changed')
        oldseg=(oldoff-base)//16;newseg=(len(data)-base)//16
        buckets=[[] for _ in range(237*31)]
        for x,y,g in zip(xx,yy,groups):
            if (x+2*y)%3==n:buckets[g].append(int(y*320+x))
        packed=b''.join(struct.pack('<H',len(v))+struct.pack(f'<{len(v)}H',*v) for v in buckets)
        if len(packed)>65535:raise ValueError('Water projection exceeds real-mode segment')
        refs=0
        for i in range(header[3]):
            offset,segment=struct.unpack_from('<HH',data,header[12]+i*4);at=base+segment*16+offset
            if struct.unpack_from('<H',data,at)[0]==oldseg:
                struct.pack_into('<H',data,at,newseg);refs+=1
        if refs!=1:raise ValueError('Unexpected water table relocation count')
        data.extend(packed);data.extend(bytes((-len(data))%16))
        reports.append({'table':n+1,'bytes':len(packed),'pixels':sum(map(len,buckets))})
    struct.pack_into('<HH',data,2,len(data)%512,(len(data)+511)//512)
    struct.pack_into('<H',data,18,0)
    Image.fromarray(domain.astype(np.uint8)*255).save(output/'water-projection-mask.png')
    (output/'water-projection.json').write_text(json.dumps({'leaf_occlusion':'replaced','tape_holes':'transparent','shadow':'offset (x=-18,y=9), separate water/text palette banks','tables':reports,'reserved_original_bss_and_stack':reserved_end},indent=2)+'\n')
    return bytes(data)


def submerged_ink(water_colors):
    """VGA palette/LUT: water caustics modulate every bevel shade, including shadow."""
    samples=[]
    levels=(13,22,31,40,48,56,63)
    for shadow in (False,True):
        for color in np.asarray(water_colors,dtype=float):
            light=float(color@np.array([.2126,.7152,.0722]))
            transmission=.15+.85*min(1,light/50)
            for level in levels:
                mixed=.60*color+.65*level*np.array([.72,.88,1.])*transmission
                if shadow:mixed*=.30
                samples.append(np.clip(np.rint(mixed),0,63).astype(np.uint8))
    swatches=Image.fromarray(np.array(samples,dtype=np.uint8)[None,:,:]*4).quantize(colors=31,dither=Image.Dither.NONE)
    palette=np.array(swatches.getpalette()[:93],dtype=np.uint8).reshape(31,3)//4
    indices=np.asarray(swatches).ravel()+129
    lookup=np.zeros((32,8),dtype=np.uint8)
    lookup[:,0]=np.arange(32)
    lookup[1:31,1:]=indices.reshape(30,7)
    return palette,lookup.tobytes()


def shaded_projector(exe,output):
    """Redirect only the pixel walker; retain original fades, UVs and cues."""
    output=Path(output)
    subprocess.run(['nasm','-I',str(output.resolve())+'/', '-f','bin',str(HERE/'full-scenes/water-projector.asm'),'-o',str(output/'water-projector.bin')],check=True)
    signature=bytes.fromhex('1e 8e d8 b8 00 a0 8e c0 8e e1 8e ea ba b3 1c')
    if exe.count(signature)!=1:raise ValueError('Water pixel walker entry changed')
    entry=exe.index(signature);data=bytearray(exe)
    h=struct.unpack_from('<14H',data);base=h[4]*16
    reloc=h[12]+h[3]*4
    if reloc+4>base:raise ValueError('No header room for projector relocation')
    data.extend(bytes((-len(data))%16));segment=(len(data)-base)//16
    data.extend((output/'water-projector.bin').read_bytes())
    data[entry:entry+5]=b'\xea'+struct.pack('<HH',0,segment)
    site=entry+3-base
    struct.pack_into('<HH',data,reloc,site%16,site//16)
    struct.pack_into('<H',data,6,h[3]+1)
    struct.pack_into('<HH',data,2,len(data)%512,(len(data)+511)//512)
    return bytes(data)


def water(released,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    old=(ROOT/'FOREST/HILLBACK.CLX').read_bytes()
    draft=Image.open(HERE/'assets/full-demo/art/water-draft.png').convert('RGB').resize((320,200),Image.Resampling.LANCZOS)
    tape,shadow=tape_masks(draft)
    rgb=np.asarray(draft)
    # The released fade reveals indices 32+ first, then 0..31 and 128..159.
    # Keep BOTH water banks in the latter group; tape alone owns the first.
    def quantize_region(mask,count):
        samples=Image.fromarray(rgb[mask][None,:,:]).quantize(colors=count,dither=Image.Dither.NONE)
        colors=np.array(samples.getpalette()[:count*3],dtype=np.uint8).reshape(count,3)
        return np.asarray(samples).ravel(),colors//4
    water_indices,water_colors=quantize_region(~tape,15)
    tape_indices,tape_colors=quantize_region(tape,31)
    pixels=np.zeros((200,320),dtype=np.uint8)
    pixels[~tape]=water_indices+1
    pixels[shadow]+=15
    pixels[tape]=tape_indices+32
    palette=bytearray(768)
    for i,c in enumerate(water_colors,1):
        palette[i*3:i*3+3]=bytes(c)
        palette[(129+i)*3:(130+i)*3]=bytes(min(63,30+int(v)//2) for v in c)
        palette[(15+i)*3:(16+i)*3]=bytes(round(int(v)*.30) for v in c)
        palette[(144+i)*3:(145+i)*3]=bytes(round(min(63,30+int(v)//2)*.30) for v in c)
    for i,c in enumerate(tape_colors,32):palette[i*3:i*3+3]=bytes(c)
    pixels=pixels.tobytes()
    # All water-modulated ink colors remain in the original second-stage fade.
    ink,lookup=submerged_ink(water_colors)
    palette[129*3:160*3]=ink.tobytes()
    (output/'water-blend.bin').write_bytes(lookup)
    new=old[:10]+palette+pixels
    exe=replace_once(Path(released).read_bytes(),old,new)
    exe=shaded_projector(water_projection(exe,draft,output),output)
    (output/'MNTSCRL.EXE').write_bytes(exe)
    strip=bytearray((ROOT/'MAIN/DATA/O2.SCI').read_bytes())
    im=Image.open(HERE/'assets/full-demo/art/water-text-shaded.png').convert('L')
    if im.size!=(640,32) or np.asarray(im).max()>7:raise ValueError('Invalid shaded water lettering')
    strip[778:778+640*32]=im.tobytes()
    (output/'O2.SCI').write_bytes(strip)
    return [output/'MNTSCRL.EXE',output/'O2.SCI']


def tape_leader(exe):
    """Replace the frozen final column with a repeating blank sprocket leader."""
    old=bytes.fromhex('81 3e 8e 52 86 01 73 04 ff 06 8e 52')
    if exe.count(old)!=1:raise ValueError('Released tape column clamp changed')
    entry=exe.index(old);data=bytearray(exe);h=struct.unpack_from('<14H',data);base=h[4]*16
    reloc=h[12]+4*h[3]
    if reloc+4>base:
        data[base:base]=bytes(16)
        struct.pack_into('<H',data,8,h[4]+1)
        base+=16;entry+=16
    data.extend(bytes(h[5]*16));data.extend(bytes((-len(data))%16))
    segment=(len(data)-base)//16
    # cmp scp,383; jb increment; mov scp,319; increment: inc scp; retf
    data.extend(bytes.fromhex('81 3e 8e 52 7f 01 72 06 c7 06 8e 52 3f 01 ff 06 8e 52 cb'))
    data[entry:entry+12]=b'\x9a'+struct.pack('<HH',0,segment)+b'\x90'*7
    site=entry+3-base;struct.pack_into('<HH',data,reloc,site%16,site//16)
    struct.pack_into('<H',data,6,h[3]+1)
    struct.pack_into('<HH',data,2,len(data)%512,(len(data)+511)//512)
    struct.pack_into('<H',data,18,0)
    return bytes(data)


def tape_center(x):
    return 17+round(3*math.sin(x/47)) if x<320 else 17+round(2*math.sin((x-320)*math.tau/64))


def round_punch(image,x,y,radius):
    # Subpixel coverage retains a round rim when the old projector magnifies it.
    for py in range(max(0,y-2),min(35,y+3)):
        for px in range(max(0,x-2),min(400,x+3)):
            coverage=sum((px+(sx+.5)/8-.5-x)**2+(py+(sy+.5)/8-.5-y)**2<radius**2
                         for sy in range(8) for sx in range(8))/64
            if coverage>=.70:image.putpixel((px,py),0)
            elif coverage>0:
                old=image.getpixel((px,py))
                if old>=192:image.putpixel((px,py),192+round((old-192)*(1-coverage)))


def tape(released,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    old=(ROOT/'WATER/MIEKKA.SCI').read_bytes();new=bytearray(old)
    message=b'THIS TAPE CANNOT PROVE WHAT IT SAYS'
    # Native parameterized sprite: 8 data tracks, one smaller sprocket track.
    # Rows are bytes left to right, track order LSB to MSB from top to bottom.
    image=Image.new('P',(400,35),0);draw=ImageDraw.Draw(image)
    for x in range(400):
        center=tape_center(x)
        for y in range(max(0,center-14),min(35,center+15)):
            light=round(35+20*math.cos((y-center)/13*math.pi/2))
            image.putpixel((x,y),192+light)
    tracks=[-12,-9,-6,0,3,6,9,12]
    for x in range(0,400,8):
        center=tape_center(x)
        round_punch(image,x,center-3,.65)
    for i,value in enumerate(message):
        x=24+i*8;center=tape_center(x)
        for bit,dy in enumerate(tracks):
            if value&(1<<bit):round_punch(image,x,center+dy,1.35)
    for i in range(64):
        new[10+(192+i)*3:13+(192+i)*3]=bytes((i,min(63,round(i*.88)),min(63,round(i*.59))))
    new[778:778+400*35]=image.tobytes()
    exe=replace_once(Path(released).read_bytes(),old,bytes(new))
    exe=tape_leader(exe)
    (output/'RAYSCRL.EXE').write_bytes(exe)
    (output/'tape-encoding.json').write_text(json.dumps({'text':message.decode(),'encoding':'ASCII, eight data tracks; LSB first top to bottom; bytes left to right','row_x':'24+8*i','center_y':'17+round(3*sin(x/47))','track_y_offsets':tracks,'feed_y_offset':-3,'feed_x':'0..392 every 8 pixels; continues on blank leader','hole_radii':{'feed':.65,'data':1.35},'leader_columns':[320,383],'leader_center_y':'17+round(2*sin((x-320)*tau/64))'},indent=2)+'\n')
    image.putpalette([v*4 for v in new[10:778]]);image.resize((800,70)).save(output/'tape-preview.png')
    return [output/'RAYSCRL.EXE']
