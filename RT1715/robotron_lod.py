"""Closed, deliberately modelled exterior LODs for the 16-bit DOS renderer.

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
    # Subdivide the sloping deck while retaining shared boundary vertices.
    vertices=[];faces=[]
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
    # Match the top's boundary subdivisions on the sides: no T-junctions
    # whose rounded screen projections could leave pinholes under depth testing.
    ring=sorted({p for p in vertices if abs(p[0]-x0)<1e-6 or abs(p[0]-x1)<1e-6 or
                 abs(p[1]-y0)<1e-6 or abs(p[1]-y1)<1e-6},
                key=lambda p:np.arctan2(p[1]-(y0+y1)/2,p[0]-(x0+x1)/2))
    offset=len(vertices);vertices+=ring+[(x,y,bottom) for x,y,z in ring]
    center=len(vertices);vertices.append(((x0+x1)/2,(y0+y1)/2,bottom))
    n=len(ring)
    for i in range(n):
        j=(i+1)%n
        faces.append((offset+n+i,offset+n+j,offset+j,offset+i))
        faces.append((center,offset+n+j,offset+n+i))
    return mesh(vertices,faces)



def crt_surround(profile=None):
    from monitor_geometry import crt_surround as build
    return build(profile)


def exterior(profile=None):
    from monitor_geometry import housing,bezel as source_bezel,details,tube_back,joint as source_joint
    monitor=housing()
    joint=source_joint()
    screen,gasket=crt_surround(profile)
    bezel=source_bezel()
    return [
        ('base',mesh([(-250,-200,0),(250,-200,0),(250,200,0),(-250,200,0),
                    (-250,-200,36),(250,-200,36),(250,200,36),(-250,200,36)],
                   [(3,2,1,0),(1,2,6,5),(2,3,7,6),(3,0,4,7)]),'paint'),
        ('lid',mesh([(-250,-200,37),(250,-200,37),(250,200,37),(-250,200,37),
                    (-250,-200,130),(250,-200,130),(250,200,130),(-250,200,130)],
                   [(1,2,6,5),(2,3,7,6),(3,0,4,7),(4,5,6,7)]),'paint'),
        ('monitor',monitor,'paint'),
        ('monitor-joint',joint,'black'),
        ('bezel',bezel,'paint'),
        ('screen',screen,'pcb'),
        ('crt-rim',gasket,'black'),
        ('tube-back',tube_back(profile),'black'),
        ('keyboard',slope_box(-247,247,-455,-255,1.2,19,36,(-238,238,-445,-298)),'blue'),
        ('deck',slope_box(-238,238,-445,-298,17,19,32),'dark'),
    ]+details()


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
    def ring(xa,xb,ya,yb,z,corner):
        return [(xa+corner,ya,z),(xb-corner,ya,z),(xb,ya+corner,z),
                (xb,yb-corner,z),(xb-corner,yb,z),(xa+corner,yb,z),
                (xa,yb-corner,z),(xa,ya+corner,z)]
    vertices=ring(x0,x1,y0,y1,z0,.8)+ring(x0+bevel,x1-bevel,y0+bevel,y1-bevel,z1,.8)
    vertices+=ring(x0+bevel+.6,x1-bevel-.6,y0+bevel+2,y1-bevel-2,z1-1,.4)
    faces=[tuple(reversed(range(8))),tuple(range(16,24))]
    for layer in (0,8):
        for i in range(8):
            j=(i+1)%8
            faces.append((layer+i,layer+j,layer+j+8,layer+i+8))
    return mesh(vertices,faces)
