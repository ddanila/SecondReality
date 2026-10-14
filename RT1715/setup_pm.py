#!/usr/bin/env python3
"""Install the verified native Watcom snapshot locally; never run guest tools."""
import argparse
import hashlib
from pathlib import Path
import tarfile
import urllib.request

SHA256='f1dfab2b4ab082fc5a235fc651c1643e23250e490d620057697a9e9aaef02d44'
URL='https://github.com/open-watcom/open-watcom-v2/releases/download/Current-build/ow-snapshot.tar.xz'


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,help='Previously downloaded 2026-10-14 snapshot')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent/'build/toolchain';root.mkdir(parents=True,exist_ok=True)
    archive=args.archive or root/'ow-snapshot.tar.xz'
    if not archive.exists():
        if args.archive:parser.error('Archive does not exist')
        print('Downloading Open Watcom snapshot (about 150 MB)...',flush=True)
        urllib.request.urlretrieve(URL,archive)
    if hashlib.sha256(archive.read_bytes()).hexdigest()!=SHA256:
        raise SystemExit('Snapshot checksum differs from the tested 2026-10-14 build. Supply that archive with --archive, or install Open Watcom separately and set WATCOM32. No files extracted.')
    destination=root/'watcom';destination.mkdir(exist_ok=True)
    with tarfile.open(archive) as tar:
        for member in tar:
            name=Path(member.name)
            if name.is_absolute() or '..' in name.parts:raise ValueError('Unsafe archive path')
            if not name.parts:continue
            if name.parts[0] not in ('armo64','binl64','lib386','h') and str(name) not in ('binw/dos32a.exe',):continue
            if not (member.isfile() or member.isdir()):continue
            tar.extract(member,destination)
    print(destination)

if __name__=='__main__':main()
