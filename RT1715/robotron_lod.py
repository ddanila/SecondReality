"""Closed, deliberately modelled exterior LODs for the 16-bit painter renderer.

Panel openings are built as frames, never as convex hulls of perforated shells.
Dimensions and placement come from the canonical exported assembly (mm).
The detailed canonical meshes remain the source for the credit photographs.
"""
import numpy as np
import trimesh


def box(lo, hi):
    lo, hi = np.array(lo), np.array(hi)
    return trimesh.creation.box(extents=hi-lo, transform=trimesh.transformations.translation_matrix((lo+hi)/2))


def mesh(vertices, quads):
    return trimesh.Trimesh(vertices, [(q[0],q[i],q[i+1]) for q in quads for i in range(1,len(q)-1)], process=True)


def slope_box(x0,x1,y0,y1,bottom,front,back):
    return mesh([(x0,y0,bottom),(x1,y0,bottom),(x1,y1,bottom),(x0,y1,bottom),
                 (x0,y0,front),(x1,y0,front),(x1,y1,back),(x0,y1,back)],
                [(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)])


def frame(x0,x1,z0,z1,y0,y1,width):
    return trimesh.util.concatenate([box([x0,y0,z0],[x0+width,y1,z1]),
        box([x1-width,y0,z0],[x1,y1,z1]),
        box([x0+width,y0,z0],[x1-width,y1,z0+width]),
        box([x0+width,y0,z1-width],[x1-width,y1,z1])])


def exterior():
    # Outer monitor skins omit the front surface: the bezel and CRT fill it.
    v=[(-160,-142,180),(160,-142,180),(160,192,180),(-160,192,180),
       (-160,-142,460),(160,-142,460),(160,192,460),(-160,192,460)]
    monitor=mesh(v,[(3,2,1,0),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)])
    # A gently curved, continuous CRT surface, wound toward the viewer.
    vertices=[];faces=[]
    for j in range(7):
        z=218.5+j*211/6
        for i in range(9):
            x=-129+i*258/8
            y=-158+9*((x/129)**2+((z-324)/105.5)**2)
            vertices.append((x,y,z))
    for j in range(6):
        for i in range(8):
            a=j*9+i;faces.append((a,a+1,a+10,a+9))
    # Fascia frame leaves a real aperture for each of the two drives.
    fascia=[box([-249,-209,36],[249,-201,60]),box([-249,-209,102],[249,-201,130]),
            box([-249,-209,60],[-231,-201,102]),box([-93,-209,60],[-69,-201,102]),
            box([69,-209,60],[249,-201,102])]
    drives=[];slots=[];latches=[]
    for x in [-231,-69]:
        drives.append(box([x,-208.5,60],[x+138,-206,102]))
        slots.append(box([x+9,-209.2,78],[x+129,-208.6,82]))
        latches.append(box([x+99,-211,65],[x+106,-209,79]))
    return [
        ('base',box([-250,-200,0],[250,200,40]),'paint'),
        ('lid',mesh([(-250,-200,40),(250,-200,40),(250,200,40),(-250,200,40),
                    (-250,-200,130),(250,-200,130),(250,200,130),(-250,200,130)],
                   [(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)]),'paint'),
        ('fascia',trimesh.util.concatenate(fascia),'paint'),
        ('drives',trimesh.util.concatenate(drives),'dark'),
        ('drive-slots',trimesh.util.concatenate(slots),'black'),
        ('drive-latches',trimesh.util.concatenate(latches),'metal'),
        ('stand',box([-85,-60,135],[85,110,180]),'paint'),
        ('monitor',monitor,'paint'),
        ('bezel',frame(-151.5,151.5,188,452,-154,-142,22),'dark'),
        ('screen',mesh(vertices,faces),'pcb'),
        ('keyboard',slope_box(-247,247,-455,-255,1.2,19,36),'blue'),
        ('deck',slope_box(-238,238,-445,-298,17,19,32),'dark'),
    ]


def keycap(source):
    """Tapered key with a shallow dish; no broken thin-shell decimation."""
    lo,hi=source.bounds
    x0,y0,z0=lo;x1,y1,z1=hi
    bevel=min(2,(x1-x0)/6,(y1-y0)/6)
    vertices=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
              (x0+bevel,y0+bevel,z1),(x1-bevel,y0+bevel,z1),
              (x1-bevel,y1-bevel,z1),(x0+bevel,y1-bevel,z1),
              (x0+bevel,y0+bevel+2,z1-1),(x1-bevel,y0+bevel+2,z1-1),
              (x1-bevel,y1-bevel-2,z1-1),(x0+bevel,y1-bevel-2,z1-1)]
    return mesh(vertices,[(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),
                          (4,5,9,8),(8,9,10,11),(11,10,6,7),(4,8,11,7),(5,6,10,9)])
