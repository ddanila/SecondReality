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


def slope_box(x0,x1,y0,y1,bottom,front,back,opening=None):
    # Small top panels keep centroid sorting local to nearby raised keycaps.
    vertices=[(x0,y0,bottom),(x1,y0,bottom),(x1,y1,bottom),(x0,y1,bottom),
              (x0,y0,front),(x1,y0,front),(x1,y1,back),(x0,y1,back)]
    faces=[(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]
    regions=[(x0,x1,y0,y1)]
    if opening:
        ox0,ox1,oy0,oy1=opening
        regions=[(x0,ox0,y0,y1),(ox1,x1,y0,y1),
                 (ox0,ox1,y0,oy0),(ox0,ox1,oy1,y1)]
    for ax,bx,ay,by in regions:
        nx=int(np.ceil((bx-ax)/20));ny=int(np.ceil((by-ay)/20))
        start=len(vertices)
        for j in range(ny+1):
            y=ay+(by-ay)*j/ny
            for i in range(nx+1):
                vertices.append((ax+(bx-ax)*i/nx,y,
                                 front+(back-front)*(y-y0)/(y1-y0)))
        for j in range(ny):
            for i in range(nx):
                a=start+j*(nx+1)+i
                faces.append((a,a+1,a+nx+2,a+nx+1))
    return mesh(vertices,faces)



def crt_surround():
    """Curved glass and its surround meet along the complete curved perimeter."""
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
    # Four strips, subdivided to match the curved glass edge exactly. Extend
    # the edge by 0.25 mm under the glass to avoid fixed-point rounding cracks.
    rim_vertices=[];rim_faces=[]
    edges=[list(range(9)),[j*9+8 for j in range(7)],
           list(range(62,53,-1)),[j*9 for j in range(6,-1,-1)]]
    corners=[(-151.5,-154,188),(151.5,-154,188),
             (151.5,-154,452),(-151.5,-154,452)]
    for k,edge in enumerate(edges):
        begin=len(rim_vertices)
        for j,index in enumerate(edge):
            u=j/(len(edge)-1)
            outer=(1-u)*np.array(corners[k])+u*np.array(corners[(k+1)%4])
            point=np.array(vertices[index],float)
            # Inset along the screen plane, leaving the lip behind the glass.
            point[0]*=.998
            point[2]=324+(point[2]-324)*.998
            point[1]+=.05
            rim_vertices.extend([outer,point])
        for j in range(len(edge)-1):
            a=begin+j*2;rim_faces.append((a,a+2,a+3,a+1))
    return mesh(vertices,faces),mesh(rim_vertices,rim_faces)


def exterior():
    # Outer monitor skins omit the front surface: the bezel and CRT fill it.
    v=[(-160,-142,180),(160,-142,180),(160,192,180),(-160,192,180),
       (-160,-142,460),(160,-142,460),(160,192,460),(-160,192,460)]
    skins=[]
    for bottom,top in [(180,319),(321,460)]:
        w=[(x,y,bottom if z==180 else top) for x,y,z in v]
        quads=[(1,2,6,5),(2,3,7,6),(3,0,4,7)]
        if bottom==180: quads.append((3,2,1,0))
        if top==460: quads.append((4,5,6,7))
        skins.append(mesh(w,quads))
    monitor=trimesh.util.concatenate(skins)
    joint=mesh([(-159,-141,319),(159,-141,319),(159,191,319),(-159,191,319),
                (-159,-141,321),(159,-141,321),(159,191,321),(-159,191,321)],
               [(1,2,6,5),(2,3,7,6),(3,0,4,7)])
    # Close the housing front with a chamfer down to the bezel's outer edge.
    outer=[(-160,-142,180),(160,-142,180),(160,-142,460),(-160,-142,460)]
    inner=[(-151.5,-154,188),(151.5,-154,188),(151.5,-154,452),(-151.5,-154,452)]
    lip=mesh(outer+inner,[(i,(i+1)%4,(i+1)%4+4,i+4) for i in range(4)])
    monitor=trimesh.util.concatenate([monitor,lip])
    screen,bezel=crt_surround()
    return [
        ('base',mesh([(-250,-200,0),(250,-200,0),(250,200,0),(-250,200,0),
                    (-250,-200,36),(250,-200,36),(250,200,36),(-250,200,36)],
                   [(3,2,1,0),(1,2,6,5),(2,3,7,6),(3,0,4,7)]),'paint'),
        ('lid',mesh([(-250,-200,37),(250,-200,37),(250,200,37),(-250,200,37),
                    (-250,-200,130),(250,-200,130),(250,200,130),(-250,200,130)],
                   [(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)]),'paint'),
        ('stand',box([-85,-60,135],[85,110,180]),'paint'),
        ('monitor',monitor,'paint'),
        ('monitor-joint',joint,'black'),
        ('bezel',bezel,'dark'),
        ('screen',screen,'pcb'),
        ('keyboard',slope_box(-247,247,-455,-255,1.2,19,36,(-238,238,-445,-298)),'blue'),
        ('deck',slope_box(-238,238,-445,-298,17,19,32),'dark'),
    ]


def keycap(source, detailed=True):
    """Tapered key with a shallow dish; no broken thin-shell decimation."""
    lo,hi=source.bounds
    x0,y0,z0=lo;x1,y1,z1=hi
    bevel=min(2,(x1-x0)/6,(y1-y0)/6)
    vertices=[(x0,y0,z0),(x1,y0,z0),(x1,y1,z0),(x0,y1,z0),
              (x0+bevel,y0+bevel,z1),(x1-bevel,y0+bevel,z1),
              (x1-bevel,y1-bevel,z1),(x0+bevel,y1-bevel,z1),
              (x0+bevel,y0+bevel+2,z1-1),(x1-bevel,y0+bevel+2,z1-1),
              (x1-bevel,y1-bevel-2,z1-1),(x0+bevel,y1-bevel-2,z1-1)]
    if not detailed:
        return mesh(vertices[:8],[(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)])
    return mesh(vertices,[(3,2,1,0),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7),
                          (4,5,9,8),(8,9,10,11),(11,10,6,7),(4,8,11,7),(5,6,10,9)])
