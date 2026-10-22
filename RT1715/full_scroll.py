"""Robotron facts in original scroll slots; preserve all pacing directives."""
from pathlib import Path
from build import ROOT


def build(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    lines=(ROOT/'MAIN/DATA/ENDSCROL.TXT').read_bytes().decode('cp437').splitlines()
    # Leave original credits, greetings and distribution acknowledgements intact.
    # Replace obsolete event invitations and contact instructions with context.
    stop=lines.index('Future Crew greets the following groups:')
    slots=[i for i in range(stop) if lines[i] and not lines[i].startswith('[')]
    text=[
        'Robotron 1715 / Second Reality',
        'Original: (C) 1993 Future Crew',
        "Second Reality won Assembly'93",
        'in Finland, summer 1993.',
        'Original demo contributors:',
        'Abyss, Gore, Marvel, Pixel, Psi,',
        'Purple Motion, Skaven, Trug, Wildfire',
        'The original computer:',
        'VEB Robotron Bueromaschinenwerk',
        'Ernst Thaelmann, Soemmerda',
        'East Germany',
        'PC 1715: presented in 1984',
        'Series production from 1985',
        'U880 processor: Z80 compatible',
        '8-bit data / 16-bit addresses',
        'Keyboard, CRT and floppy storage',
        'The flyover shows the 1715M model',
        'Later 1715M: expanded memory',
        'TOS/M boot and real character ROM',
        'Captured from the DAC machine',
        'UB880 die photograph:',
        "Richi's Lab / richis-lab.de",
        'CC BY-NC 4.0; cropped and reduced',
        'Robotron artwork: review drafts',
        'Full sources and image attribution',
        'are included with this adaptation.',
        'Thanks to the original creators',
        'and computer preservation community.'
    ]
    if len(text)>len(slots):raise ValueError('Too many scroll facts')
    for j,i in enumerate(slots):lines[i]=text[j] if j<len(text) else ''
    closing=max(i for i,line in enumerate(lines) if line=='Second Reality')
    lines[closing]='Robotron 1715'
    # Preserve every line, blank spacing, speed command, and terminating marker.
    result=output/'ENDSCROL.TXT';result.write_bytes(('\r\n'.join(lines)+'\r\n').encode('cp437'))
    return result
