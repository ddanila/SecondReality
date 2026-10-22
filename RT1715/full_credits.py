"""Caption-only full-demo edits; preserve reviewed images and motion, match the original end cue."""
import hashlib,json,struct
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from build import HERE
from prepare import printable

EDITS={
    1:['Inside the Robotron 1715M','Processor, video, drives and power','The hardware behind the journey'],
    2:['Main processor','UA880 / Z80-compatible','8-bit data / 16-bit addresses'],
    21:['Robotron 1715M','A journey inside the machine','Built on Second Reality'],
}


def caption(lines):
    printable(lines);image=Image.new('L',(320,200))
    for n,line in enumerate(lines):
        for size in range((26,20,16,16)[n],5,-1):
            font=ImageFont.load_default(size=size);box=font.getbbox(line or ' ')
            if box[2]-box[0]<=312 and box[3]-box[1]<=32:break
        glyph=Image.new('L',(max(1,box[2]-box[0]),max(1,box[3]-box[1])))
        ImageDraw.Draw(glyph).text((-box[0],-box[1]),line,font=font,fill=(255,244,221,221)[n])
        if glyph.width>312:raise ValueError('Full-demo caption is too wide')
        image.paste(glyph,((320-glyph.width)//2,(12,66,110,150)[n]))
    ImageDraw.Draw(image).line((112,49,207,49),fill=85,width=1)
    return bytes(round(v*15/255) for v in image.tobytes())


def build(dos):
    dos=Path(dos);report=[]
    for number,lines in EDITS.items():
        path=dos/f'CARD{number:02}.CRD';old=path.read_bytes()
        if old[:4] not in (b'CRD1',b'CRD2') or len(old)<80772:raise ValueError('Invalid reviewed card')
        new=old[:772]+caption(lines)+old[64772:]
        assert len(new)==len(old)
        path.write_bytes(new)
        report.append({'card':number,'lines':lines,'old_sha256':hashlib.sha256(old).hexdigest(),'new_sha256':hashlib.sha256(new).hexdigest(),'unchanged':'palette, picture, reveal frames'})
    reference=json.loads((HERE/'assets/full-demo/reference-cues.json').read_text())
    end=next(r for r in reference if r['executable']=='CRED.EXE' and r['phase']=='exit')
    clock=(dos/'CRED.TIM').read_bytes()
    stop=struct.unpack_from('<H',clock,((end['order']-28)*64+end['row'])*2)[0]
    rows=(dos/'CRED.CUE').read_text().splitlines();last=list(map(int,rows[-1].split()))
    fade=last[3]-last[2];last[2:]=[stop-fade,stop]
    if not last[1]<last[2]:raise ValueError('Final full-demo credit hold is too short')
    rows[-1]=' '.join(map(str,last));(dos/'CRED.CUE').write_text('\n'.join(rows)+'\n')
    report.append({'end_order':end['order'],'end_row':end['row'],'last_card_end_cs':stop,'reason':'Match the measured original full-demo handoff; short-cut schedule is preserved.'})
    (dos.parent/'credit-editorial.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
