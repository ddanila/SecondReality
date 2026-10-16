#!/usr/bin/env python3
"""Render an effect with the same C renderer on the host, without DOS startup."""
import argparse
from pathlib import Path
import subprocess
import tempfile
from expansion import HERE,SCENES


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('scene',choices=SCENES)
    p.add_argument('--assets',type=Path,default=HERE/'build/extended/dos')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--seconds',type=float,default=14.769)
    p.add_argument('--fps',type=int,default=25)
    args=p.parse_args()
    if not 0<args.seconds<=120 or not 1<=args.fps<=70:p.error('Invalid duration or frame rate')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rt1715-effect-') as tmp:
        renderer=Path(tmp)/'effect'
        subprocess.run(['cc','-O2','-DFX_HOST',str(HERE/'effects.c'),'-o',str(renderer),'-lm'],check=True)
        command=['ffmpeg','-v','error','-y','-f','image2pipe','-vcodec','ppm','-framerate',str(args.fps),'-i','-',
                 '-vf','scale=640:480:flags=neighbor,setsar=1','-c:v','libx264','-pix_fmt','yuv420p','-crf','18',str(args.output.resolve())]
        encoder=subprocess.Popen(command,stdin=subprocess.PIPE)
        try:
            for i in range(round(args.seconds*args.fps)):
                frame=subprocess.check_output([str(renderer),str(SCENES.index(args.scene)),str(i/args.fps),str(args.seconds),'-'],cwd=args.assets)
                encoder.stdin.write(frame)
            encoder.stdin.close()
            if encoder.wait():raise RuntimeError('Preview encoder failed')
        except BaseException:
            encoder.kill();encoder.wait();raise
    print(args.output)


if __name__=='__main__':main()
