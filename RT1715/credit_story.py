"""DOS-resolution editorial diagrams and short, host-authored component reveals.

Diagrams are functional explanations, not schematics or measured wiring.
All motion finishes within 0.96 s of the hold; the remaining hold is static.
"""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

SIZE=(160,100)
INK='#dce4df'
ACCENT='#a8d3b4'
FONT=ImageFont.load_default(size=9)


def label(draw,xy,text,fill=INK):
    draw.text(xy,text,font=FONT,fill=fill)


def box(draw,rect,text):
    draw.rectangle(rect,outline=ACCENT)
    x0,y0,x1,y1=rect
    label(draw,((x0+x1-draw.textlength(text,font=FONT))/2,y0+3),text)


def arrow(draw,start,end):
    draw.line([start,end],fill=INK)
    x,y=end
    if end[0]!=start[0]:
        s=1 if end[0]>start[0] else -1
        draw.line([(x-3*s,y-2),(x,y),(x-3*s,y+2)],fill=INK)
    else:draw.line([(x-2,y-3),(x,y),(x+2,y-3)],fill=INK)


def diagram(kind,photo,progress=1):
    """A highlighted source component beside an explicitly functional diagram."""
    image=Image.new('RGB',SIZE,'black');d=ImageDraw.Draw(image)
    titles={'clock':'CPU TIMING','matrix':'A KEY TO THE COMPUTER','video':'DISPLAY DATA PATH'}
    if kind not in titles:raise ValueError('Unknown technical diagram: '+kind)
    label(d,(5,3),titles[kind],ACCENT)
    if photo is not None:
        thumb=ImageOps.contain(photo.convert('RGB'),(76,52),Image.Resampling.LANCZOS)
        image.paste(thumb,((78-thumb.width)//2,16+(52-thumb.height)//2))
    d.rectangle((3,15,77,69),outline='#ffd58c')
    if kind=='clock':
        box(d,(88,19,154,35),'CLOCK')
        arrow(d,(121,36),(121,49));box(d,(88,50,154,67),'UA880')
        label(d,(5,75),'UA880 CPU',fill='#ffd58c')
        label(d,(5,87),'3.9936 MHz reference')
        d.rectangle((88,50,154,67),outline='#ffd58c')
        if progress<1:
            y=round(36+12*progress);d.ellipse((119,y-2,123,y+2),fill='white')
            if .2<progress<.8:d.rectangle((2,14,78,70),outline='white')
    elif kind=='matrix':
        for x in range(8):d.line((94+x*7,20,94+x*7,56),fill='#5b7863')
        for y in range(13):d.line((94,20+y*3,143,20+y*3),fill='#5b7863')
        d.ellipse((113,33,117,37),fill='#ffd58c')
        label(d,(91,58),'13 x 8')
        box(d,(3,73,32,86),'KEY');arrow(d,(33,79),(46,79))
        box(d,(47,73,102,86),'UB880D');arrow(d,(103,79),(116,79))
        box(d,(117,73,156,86),'HOST')
        if progress<1:
            x=round(18+119*progress);d.ellipse((x-2,77,x+2,81),fill='#ffd58c')
            if .30<progress<.75:d.rectangle((2,14,78,70),outline='white')
        label(d,(5,89),'Illustrative key data')
    else:
        for rect,text in [((87,15,155,30),'VIDEO RAM'),((87,40,155,55),'8275'),((87,65,155,80),'CRT')]:box(d,rect,text)
        arrow(d,(121,31),(121,39));arrow(d,(121,56),(121,64))
        label(d,(5,74),'UL6516D',fill='#ffd58c')
        label(d,(5,88),'Functional view')
        d.rectangle((87,15,155,30),outline='#ffd58c')
        if progress<1:
            y=round(31+7*progress);d.ellipse((119,y-2,123,y+2),fill='white')
            if .2<progress<.8:d.rectangle((2,14,78,70),outline='white')
    d.rectangle((0,0,159,99),outline=INK)
    return image


def component_photo(output,name):
    """Crop a source-rendered component and outline its actual mask footprint."""
    import numpy as np
    photo=Image.open(output/f'{name}-photo.png').convert('RGB')
    mask=np.array(Image.open(output/f'{name}-annotation.png').convert('RGB')).astype(int)
    selected=(mask[:,:,0]>mask[:,:,1]*2+30)&(mask[:,:,2]>mask[:,:,1]*2+30)
    yy,xx=np.where(selected)
    if not len(xx):raise ValueError('Missing diagram component highlight: '+name)
    bounds=(max(0,int(xx.min())-50),max(0,int(yy.min())-45),min(960,int(xx.max())+51),min(600,int(yy.max())+46))
    # Outline in the final inset resolution, rather than losing a thin line on resize.
    photo=photo.crop(bounds);thumb=ImageOps.contain(photo,(70,48),Image.Resampling.LANCZOS)
    sx,sy=thumb.width/photo.width,thumb.height/photo.height
    ImageDraw.Draw(thumb).rectangle(((xx.min()-bounds[0])*sx,(yy.min()-bounds[1])*sy,
        min(thumb.width-1,(xx.max()-bounds[0])*sx),min(thumb.height-1,(yy.max()-bounds[1])*sy)),outline='#ffd58c')
    return thumb


def finish(cards,result,output):
    """Postprocess separately so geometry cache never accumulates decorations."""
    output=Path(output)
    workstation=(Image.open(output/'workstation.png').convert('RGB').resize(SIZE,Image.Resampling.LANCZOS)
                 if any(c.get('view',{}).get('reveal') for c in cards) else None)
    for card,item in zip(cards,result):
        view=card.get('view',{});original=Image.open(item['image']).convert('RGB').resize(SIZE,Image.Resampling.LANCZOS)
        picture=original
        if view.get('diagram'):
            photo=component_photo(output,card['image'])
            picture=diagram(view['diagram'],photo)
            if view['diagram'] in ('clock','matrix','video'):
                frames=[]
                for n in range(16):
                    path=output/f'{card["image"]}-signal-{n}.png'
                    diagram(view['diagram'],photo,n/15).save(path);frames.append(str(path))
                item['reveal_frames']=frames;item['reveal_cs']=96
        if view.get('cutaway'):
            frames=[output/'cutaway'/f'{n:02}.png' for n in range(16)]
            picture=Image.open(frames[-1]).convert('RGB')
            item['reveal_frames']=[str(p) for p in frames];item['reveal_cs']=96
        if view.get('closing'):
            picture=Image.new('RGB',SIZE,'black')
            # Keep the unique closing camera and give its silhouette breathing room.
            thumb=ImageOps.contain(original.crop((2,15,158,98)),(140,72),Image.Resampling.LANCZOS)
            picture.paste(thumb,((160-thumb.width)//2,14))
            d=ImageDraw.Draw(picture);label(d,(43,3),'ROBOTRON 1715M',ACCENT)
            d.line((48,92,111,92),fill='#607568')
        path=output/(card['image']+'-story.png');picture.save(path);item['image']=str(path)
        if view.get('reveal'):
            board_path=output/(card['image']+'-locator.png')
            if not board_path.is_file():raise ValueError('Reveal needs full board render: '+card['image'])
            board=Image.open(board_path).convert('RGB')
            # The source locator still has the OpenSCAD background removed.
            import numpy as np
            pixels=np.array(board);pixels[np.all(pixels==[29,31,33],axis=2)]=0
            board=Image.fromarray(pixels);board=board.crop(board.getbbox())
            frames=[]
            for n in range(9):
                t=n/8
                if t<.625:
                    u=t/.625;u=u*u*(3-2*u)
                    frame=Image.blend(workstation,Image.new('RGB',SIZE),u)
                    thumb=ImageOps.contain(board,(round(52+100*u),round(32+46*u)),Image.Resampling.LANCZOS)
                    layer=Image.new('RGB',SIZE);layer.paste(thumb,((160-thumb.width)//2,(100-thumb.height)//2))
                    frame=Image.blend(frame,layer,u)
                    d=ImageDraw.Draw(frame);d.rectangle((1,1,158,13),fill='black')
                    label(d,(5,3),'INSIDE THE MACHINE',ACCENT)
                else:
                    layer=Image.new('RGB',SIZE);thumb=ImageOps.contain(board,(152,78),Image.Resampling.LANCZOS)
                    layer.paste(thumb,((160-thumb.width)//2,(100-thumb.height)//2))
                    frame=Image.blend(layer,picture,(t-.625)/.375)
                ImageDraw.Draw(frame).rectangle((0,0,159,99),outline=INK)
                path=output/f'{card["image"]}-reveal-{n}.png';frame.save(path);frames.append(str(path))
            item['reveal_frames']=frames;item['reveal_cs']=80
    return result
