"""Small host-rasterized key legends converted to coplanar DOS polygons.

Pillow's bundled font avoids machine-dependent fonts. Symbols missing from
that font use explicit compact bitmaps. Horizontal runs merge vertically to
keep conventional-memory and face counts small.
"""
from PIL import Image, ImageDraw, ImageFont

SYMBOLS={
 '←':['00100','01000','11111','01000','00100'],
 '→':['00100','00010','11111','00010','00100'],
 '↑':['00100','01110','10101','00100','00100'],
 '↓':['00100','00100','10101','01110','00100'],
 '↔':['01010','10001','11111','10001','01010'],
 '↱':['00100','00110','11111','10010','10000'],
 '↵':['00001','00101','01111','00100','00000'],
 '⇤':['10100','11000','11111','11000','10100'],
 '⇥':['00101','00011','11111','00011','00101'],
 'Ⓡ':['0111110','1100011','1011101','1010101','1011001','1101011','0111110'],
}


def bitmap(lines):
    font=ImageFont.load_default(size=8)
    rendered=[]
    for line in lines:
        chars=[]
        for char in line:
            if char in SYMBOLS:
                rows=SYMBOLS[char]
                im=Image.new('1',(len(rows[0]),len(rows)))
                im.putdata([v=='1' for row in rows for v in row])
            else:
                b=font.getbbox(char)
                im=Image.new('1',(max(1,b[2]-b[0]),max(1,b[3]-b[1])))
                ImageDraw.Draw(im).text((-b[0],-b[1]),char,font=font,fill=1)
            chars.append(im)
        if not chars: continue
        im=Image.new('1',(sum(c.width for c in chars)+len(chars)-1,max(c.height for c in chars)))
        x=0
        for c in chars:
            im.paste(c,(x,im.height-c.height));x+=c.width+1
        rendered.append(im)
    if not rendered: return Image.new('1',(1,1))
    out=Image.new('1',(max(i.width for i in rendered),sum(i.height for i in rendered)+2*(len(rendered)-1)))
    y=0
    for im in rendered:
        out.paste(im,((out.width-im.width)//2,y));y+=im.height+2
    return out


def rectangles(im):
    """Exactly cover the lit bitmap cells with non-overlapping rectangles."""
    active={};result=[]
    for y in range(im.height+1):
        runs=[];x=0
        if y<im.height:
            while x<im.width:
                if not im.getpixel((x,y)): x+=1;continue
                start=x
                while x<im.width and im.getpixel((x,y)): x+=1
                runs.append((start,x))
        current=set(runs)
        for run,top in active.items():
            if run not in current: result.append((run[0],top,run[1],y))
        active={run:active.get(run,y) for run in runs}
    return result


def polygons(lines,bounds,scale):
    im=bitmap(lines);lo,hi=bounds
    # Entire legend sits on the flat part of the key's dished top.
    unit=min(1.05,(hi[0]-lo[0]-6)/im.width,(hi[1]-lo[1]-9)/im.height)
    cx=(hi[0]+lo[0])/2;cy=(hi[1]+lo[1])/2;z=hi[2]-1+.16
    faces=[]
    for x0,y0,x1,y1 in rectangles(im):
        left=cx+(x0-im.width/2)*unit;right=cx+(x1-im.width/2)*unit
        top=cy+(im.height/2-y0)*unit;bottom=cy+(im.height/2-y1)*unit
        faces.append([(round(x*scale),round(y*scale),round(z*scale))
                      for x,y in [(left,bottom),(right,bottom),(right,top),(left,top)]])
    return faces
