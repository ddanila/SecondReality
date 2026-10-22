"""Replace the released lens background while preserving every code byte."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image
from build import HERE,ROOT


def build(released, output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    binary=Path(released).read_bytes()
    original=(ROOT/'LENS/LENS.EXB').read_bytes()
    at=binary.find(original)
    if at<0 or binary.find(original,at+1)>=0:raise ValueError('Unique released background not found')
    image=Image.open(HERE/'assets/full-demo/lens/ub880-die.jpg').convert('RGB')
    # 320x200 VGA pixels display with a 1.2 vertical scale.
    width=round(200*1.2*image.width/image.height)
    frame=Image.new('RGB',(320,200));frame.paste(image.resize((width,200),Image.Resampling.LANCZOS),((320-width)//2,0))
    quant=frame.quantize(colors=64,method=Image.Quantize.MEDIANCUT,dither=Image.Dither.NONE)
    data=original[:16]+bytes(v//4 for v in quant.getpalette()[:192])+bytes(576)+quant.tobytes()
    if len(data)!=len(original):raise ValueError('Lens asset length changed')
    patched=binary[:at]+data+binary[at+len(data):]
    (output/'LNS&ZOOM.EXE').write_bytes(patched)
    quant.convert('RGB').resize((640,480),Image.Resampling.NEAREST).save(output/'lens-vga.png')
    (output/'lens.json').write_text(json.dumps({'asset_offset':at,'asset_bytes':len(data),'code_unchanged':True,'released_sha256':hashlib.sha256(binary).hexdigest(),'image_sha256':hashlib.sha256(data).hexdigest()},indent=2)+'\n')
    return output/'LNS&ZOOM.EXE'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--released',type=Path,required=True);p.add_argument('--output',type=Path,default=HERE/'build/full-lens');a=p.parse_args();print(build(a.released,a.output))
