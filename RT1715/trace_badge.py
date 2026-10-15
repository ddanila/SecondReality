#!/usr/bin/env python3
"""Trace the white front badge from the canonical owner photograph."""
from pathlib import Path
import argparse,hashlib,json
import numpy as np
from PIL import Image

HERE=Path(__file__).resolve().parent

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('photo',type=Path,nargs='?',default=HERE.parent.parent/'3d-models/models/robotron-1715m/reference/photos/PXL_20261013_113529099.jpg')
    args=p.parse_args();box=(230,2190,2280,2370)
    with Image.open(args.photo) as im:a=np.asarray(im.convert('RGB').crop(box))
    mask=Image.fromarray(a.min(axis=2)>235).rotate(1.1,resample=Image.Resampling.NEAREST,expand=True)
    mask=mask.crop(mask.getbbox()).resize((384,22),Image.Resampling.LANCZOS).point(lambda v:255 if v>=128 else 0,'1')
    out=HERE/'assets/robotron';mask.save(out/'badge.png')
    (out/'badge.json').write_text(json.dumps({'source':'3d-models/models/robotron-1715m/reference/photos/'+args.photo.name,
        'sha256':hashlib.sha256(args.photo.read_bytes()).hexdigest(),'crop':box,'rotation_degrees':1.1,
        'method':'White ink threshold min(R,G,B)>235; straighten baseline, crop bounds, resample to 384x22. Photo-derived glyphs and spacing.',
        'placement_mm':{'center_x':-188.5,'center_z':49,'width':82,'height':4.6,'y':-211},
        'uncertainty':'Photo estimate relative to drive front width; not a physical measurement.'},indent=2)+'\n')

if __name__=='__main__':main()
