#!/usr/bin/env python3
"""Make a shareable MP4 from a completed headless DOSBox-X capture."""
import argparse
from pathlib import Path
import shutil
import subprocess


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture',type=Path)
    parser.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'build/robotron-preview.mp4')
    args=parser.parse_args()
    ffmpeg=shutil.which('ffmpeg')
    if not ffmpeg: parser.error('ffmpeg is required')
    videos=sorted(args.capture.glob('*.avi'))
    waves=sorted(args.capture.glob('*.wav'))
    if not videos or len(waves)!=1: parser.error('Expected AVI files and one continuous WAV recording')
    command=[ffmpeg,'-v','error','-y']
    for path in [*videos,waves[0]]: command+=['-i',str(path)]
    filters=[f'[{i}:v]setpts=PTS-STARTPTS,scale=640:480:flags=neighbor,setsar=1,fps=35[v{i}]'
             for i in range(len(videos))]
    filters.append(''.join(f'[v{i}]' for i in range(len(videos)))+
                   f'concat=n={len(videos)}:v=1:a=0[out]')
    args.output.parent.mkdir(parents=True,exist_ok=True)
    command+=['-filter_complex',';'.join(filters),'-map','[out]','-map',f'{len(videos)}:a',
              '-c:v','libx264','-preset','fast','-crf','18','-c:a','aac','-b:a','160k',
              '-movflags','+faststart','-shortest',str(args.output)]
    subprocess.run(command,check=True)
    print(args.output.resolve())


if __name__=='__main__':
    main()
