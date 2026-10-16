#!/usr/bin/env python3
"""Host-build FLIGHT.EXE beside an existing runtime without changing other cuts."""
import argparse
from pathlib import Path
import shutil
import subprocess
import tempfile

from build import HERE, ROOT, masm_source, tool


def launcher():
    code = masm_source(True, True)
    anchor = '        mov     si,OFFSET exe22       ; CREDITS/MAIN.C: illustrated cards'
    if code.count(anchor) != 1:
        raise ValueError('Flight launcher credit boundary changed')
    # Keep flight error handling and the resident player's normal fade/cleanup.
    return code.replace(anchor, '        jmp local_global_rt_sequence_done\n' + anchor)


def build(dos):
    dos = Path(dos).resolve()
    for name in ('U2E.EXE', 'REALITY.FC'):
        if not (dos / name).is_file():
            raise ValueError('Missing base runtime: ' + str(dos / name))
    with tempfile.TemporaryDirectory(prefix='rt1715-flight-') as temp:
        work = Path(temp)
        (work / 'FLIGHT.ASM').write_text(launcher(), encoding='cp437')
        shutil.copyfile(ROOT / 'MAIN/STMIK.300', work / 'STMIK.OBJ')
        subprocess.run([tool('jwasm'), '-q', '-Cp', '-omf', '-FoFLIGHT.OBJ', 'FLIGHT.ASM'], cwd=work, check=True)
        subprocess.run([tool('wlink'), 'format', 'dos', 'option', 'quiet', 'name',
                        str(dos / 'FLIGHT.EXE'), 'file', 'FLIGHT.OBJ', 'file', 'STMIK.OBJ'], cwd=work, check=True)
    print(dos / 'FLIGHT.EXE')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dos-dir', type=Path, default=HERE / 'build/dos')
    build(parser.parse_args().dos_dir)
