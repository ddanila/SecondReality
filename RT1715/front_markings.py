"""Small front-panel ink meshes, shared by flight and credit photographs."""
import trimesh
from legends import bitmap, rectangles
from PIL import Image


def badge_bitmap():
    # Explicit 5x7 lettering: the tiny proportional font loses closed counters
    # when rasterized at VGA sizes (notably the lowercase o and digits).
    glyphs={
        "r":["00000","00000","10110","11001","10000","10000","10000"],
        "o":["00000","00000","01110","10001","10001","10001","01110"],
        "b":["10000","10000","10110","11001","10001","10001","11110"],
        "t":["01000","01000","11110","01000","01000","01001","00110"],
        "n":["00000","00000","11110","10001","10001","10001","10001"],
        "1":["00100","01100","00100","00100","00100","00100","01110"],
        "7":["11111","00001","00010","00100","01000","01000","01000"],
        "5":["11111","10000","10000","11110","00001","00001","11110"],
        "M":["10001","11011","10101","10101","10001","10001","10001"],
        " ":["00000"]*7,
    }
    text="robotron 1715M";im=Image.new("1",(len(text)*6-1,7))
    for i,char in enumerate(text):
        for y,row in enumerate(glyphs[char]):
            for x,value in enumerate(row):im.putpixel((i*6+x,y),value=="1")
    return im



def markings():
    # Model name uses the clear strip above the drives. Control legends follow
    # the canonical front_labels() coordinates; control ink is 0.12 mm ahead of skin.
    # Raise the badge 2 mm: pixel-rounded projection otherwise makes its
    # tiny strokes intersect the much larger fascia depth plane at grazing angles.
    for name,text,cx,z,height,y in [
        ('model-name','robotron 1715M',-119,112,10,-211.0),
        ('reset-label','RESET',-208,4.8,3.2,-200.12),
        ('power-label','POWER',207,4.8,3.2,-200.12),
        ('off-label','OFF',175,17,3,-200.12),
        ('on-label','ON',238,17,3,-200.12),
    ]:
        ink=badge_bitmap() if name=='model-name' else bitmap([text]);unit=height/ink.height
        pieces=[]
        for x0,y0,x1,y1 in rectangles(ink):
            left=cx+(x0-ink.width/2)*unit;right=cx+(x1-ink.width/2)*unit
            top=z+(ink.height/2-y0)*unit;bottom=z+(ink.height/2-y1)*unit
            part=trimesh.creation.box(extents=[right-left,.04,top-bottom])
            part.apply_translation([(left+right)/2,y+.02,(bottom+top)/2])
            pieces.append(part)
        mesh=trimesh.util.concatenate(pieces)
        faces=mesh.faces
        # Scene objects have a 500-vertex limit, including separate glyphs.
        for i in range(0,len(faces),384):
            yield f'{name}-{i//384}',mesh.submesh([range(i,min(i+384,len(faces)))],append=True),'black','marking'
