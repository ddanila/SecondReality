"""Host-generated RGB555 nearest-palette table for coverage-filtered markings."""
import numpy as np


def lookup(palette):
    palette=np.frombuffer(palette,dtype=np.uint8).reshape(256,3).astype(np.int32)
    values=np.arange(32768,dtype=np.int32)
    rgb=np.stack(((values>>10)&31,(values>>5)&31,values&31),axis=1)*2+1
    result=[]
    for block in np.array_split(rgb,64):
        delta=block[:,None,:]-palette[None,:252,:]
        result.append(np.argmin(np.sum(delta*delta,axis=2),axis=1).astype(np.uint8))
    return np.concatenate(result).tobytes()
