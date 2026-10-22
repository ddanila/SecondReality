#!/usr/bin/env python3
"""Generate the seven-shade scroll bitmap; normal builds use the checked-in PNG."""
import argparse
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy.ndimage import distance_transform_edt, shift

TEXT='EIGHT BITS. A WHOLE NEW WORLD.'

def build(font_path, output):
    font=ImageFont.truetype(str(font_path),30)
    image=Image.new('L',(640,32))
    ImageDraw.Draw(image).text((8,-2),TEXT,font=font,fill=255)
    mask=np.asarray(image)>127
    if mask[:,630:].any():raise ValueError('Font exceeds original scroll width')
    distance=distance_transform_edt(mask)
    gy,gx=np.gradient(distance)
    pixels=np.zeros(mask.shape,dtype=np.uint8)
    pixels[shift(mask.astype(np.uint8),(2,2),order=0)>0]=1
    pixels[mask]=np.clip(np.rint(4+(gx[mask]+gy[mask])*2),2,7)
    Image.fromarray(pixels).save(output)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--font',type=Path,required=True)
    parser.add_argument('--output',type=Path,default=Path(__file__).parent/'assets/full-demo/art/water-text-shaded.png')
    args=parser.parse_args();build(args.font,args.output)
