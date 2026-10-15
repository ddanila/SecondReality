"""DOS monitor profiles following the canonical SCAD enclosure and CRT.

Rings share vertices at all material boundaries. The CRT uses the source's
superellipse and ellipsoid instead of a rectangular paraboloid approximation.
"""
import numpy as np
import trimesh


def surface(rings,center=None):
    vertices=list(np.concatenate(rings));faces=[];n=len(rings[0])
    if center is not None:
        c=len(vertices);vertices.append(center)
        faces.extend((c,i,(i+1)%n) for i in range(n))
    for k in range(len(rings)-1):
        for i in range(n):
            a=k*n+i;b=k*n+(i+1)%n
            faces.extend([(a,a+n,b+n),(a,b+n,b)])
    m=trimesh.Trimesh(vertices,faces,process=True)
    m.update_faces(m.nondegenerate_faces())
    m.remove_unreferenced_vertices()
    return m


def rounded(w,h,r,n=32):
    # Equal corner-angle samples retain straight horizontal/vertical sections.
    points=[]
    for cx,cz,start in [(w/2-r,h/2-r,0),(-w/2+r,h/2-r,90),
                        (-w/2+r,-h/2+r,180),(w/2-r,-h/2+r,270)]:
        for t in np.linspace(start,start+90,n//4):
            a=np.radians(t);points.append((cx+r*np.cos(a),cz+r*np.sin(a)))
    return np.array(points)


def outline(w,h,power=4.5,n=32):
    t=np.arange(n)*2*np.pi/n
    return np.column_stack((w/2*np.sign(np.cos(t))*abs(np.cos(t))**(2/power),
                            h/2*np.sign(np.sin(t))*abs(np.sin(t))**(2/power)))


def ring(points,y,z=320):
    return np.column_stack((points[:,0],np.broadcast_to(y,len(points)),points[:,1]+z))


def glass_depth(points,depth=18,radii=(700,650,600)):
    return depth-radii[2]+radii[2]*np.sqrt(1-(points[:,0]/radii[0])**2-(points[:,1]/radii[1])**2)


def crt_surround(profile=None):
    profile=profile or {}
    size=profile.get('size',[258,211]);power=profile.get('outlinePower',4.5)
    position=profile.get('position',[0,-140,324]);depth=profile.get('depth',18)
    radii=profile.get('radii',[700,650,600])
    edge=outline(*size,power=power)
    rings=[]
    for u in np.linspace(.2,1,5):
        xy=edge*u
        rings.append(ring(xy,position[1]-glass_depth(xy,depth,radii),position[2]))
    glass=surface(rings,center=[0,position[1]-depth,position[2]])
    # A continuous dark gasket, sharing the exact glass boundary. Its outer
    # skirt runs back to the source bezel return; no uncovered corner wedges.
    outer=outline(size[0]+1,size[1]+1,power=power)
    gasket=surface([rings[-1],ring(outer,position[1]-glass_depth(outer,depth,radii),position[2]),
                    ring(outer,-142,position[2])])
    # Ring winding is chosen for the outward (-Y) front surface.
    if np.mean(glass.face_normals[:,1])>0:glass.invert()
    if np.mean(gasket.face_normals[:,1])>0:gasket.invert()
    return glass,gasket


def collar(back,front):
    """Join differently sampled closed rings without leaving an open rear rim."""
    def ordered(points):
        points=np.unique(points,axis=0)
        angles=np.mod(np.arctan2(points[:,2]-320,points[:,0]),2*np.pi)
        order=np.argsort(angles)
        return points[order],angles[order]
    a,aa=ordered(back);b,bb=ordered(front);n=len(a);m=len(b)
    vertices=np.concatenate((a,b));faces=[];i=j=0
    while i<n or j<m:
        an=aa[(i+1)%n]+(2*np.pi if i+1>=n else 0) if i<n else np.inf
        bn=bb[(j+1)%m]+(2*np.pi if j+1>=m else 0) if j<m else np.inf
        if an<bn:
            faces.append((i%n,(i+1)%n,n+j%m));i+=1
        else:
            faces.append((i%n,n+(j+1)%m,n+j%m));j+=1
    mesh=trimesh.Trimesh(vertices=vertices,faces=faces,process=True)
    radial=mesh.triangles_center-np.array([0,0,320])
    if np.mean(np.sum(mesh.face_normals[:,[0,2]]*radial[:,[0,2]],axis=1))<0:mesh.invert()
    return mesh


def bezel():
    # Trace each profile with the same angular rays, so the rounded-rectangle
    # roll and superelliptic opening align without twisted connecting strips.
    def radial(w,h,r):
        poly=rounded(w,h,r,128);result=[]
        for direction in outline(274,227):
            d=direction/np.linalg.norm(direction);best=[]
            for a,b in zip(poly,np.roll(poly,-1,axis=0)):
                mat=np.column_stack((d,a-b))
                if abs(np.linalg.det(mat))<1e-9:continue
                distance,u=np.linalg.solve(mat,a)
                if distance>=0 and 0<=u<=1:best.append(distance)
            result.append(d*min(best))
        return np.array(result)
    profiles=[ring(radial(303,264,19),-145),ring(radial(302,263,21),-150),
              ring(radial(296,257,22),-153),ring(radial(290,239,20),-153,324),
              ring(outline(259,212),-142,324)]
    m=surface(profiles)
    if np.mean(m.face_normals[:,1])>0:m.invert()
    return trimesh.util.concatenate([m,collar(ring(rounded(300,260,0),-142),profiles[0])])


def housing():
    # Rounded 320x334x280 shell, 10 mm bend radius, split at source seam.
    rings=[]
    for y in [-142,-141.24,-139.07,-135.83,-132,182,185.83,189.07,191.24,192]:
        offset=max(-132-y,y-182,0)
        radius=np.sqrt(max(0,100-offset*offset))
        rings.append(ring(rounded(300+2*radius,260+2*radius,radius),y))
    shell=surface(rings)
    # Rear cap; front stays open behind the rolled bezel and CRT.
    rear=trimesh.Trimesh(vertices=[*rings[-1],[0,192,320]],
        faces=[(32,(i+1)%32,i) for i in range(32)],process=True)
    shell=trimesh.util.concatenate([shell,rear])
    # Correct outward normals independently of front-facing ring convention.
    if shell.volume<0:shell.invert()
    def clipped(level,sign):
        vertices=[];faces=[]
        for tri in shell.triangles:
            polygon=[]
            for a,b in zip(tri,np.roll(tri,-1,axis=0)):
                inside=(a[2]-level)*sign>=0
                if inside:polygon.append(a)
                if inside!=((b[2]-level)*sign>=0):
                    polygon.append(a+(b-a)*(level-a[2])/(b[2]-a[2]))
            offset=len(vertices);vertices.extend(polygon)
            faces.extend((offset,offset+i,offset+i+1) for i in range(1,len(polygon)-1))
        return trimesh.Trimesh(vertices,faces,process=True)
    return trimesh.util.concatenate([clipped(319,-1),clipped(321,1)])


def details():
    # Dark recessed appearance of the 25 source top slots (4 x 60 mm).
    vertices=[];faces=[]
    for x in range(-120,121,10):
        i=len(vertices);vertices.extend([(x-2,65,460.1),(x+2,65,460.1),(x+2,125,460.1),(x-2,125,460.1)])
        faces.extend([(i,i+1,i+2),(i,i+2,i+3)])
    vents=trimesh.Trimesh(vertices,faces,process=True)
    pedestal=trimesh.creation.annulus(r_min=77,r_max=85.5,height=45,sections=24)
    # Source stand tapers 171 -> 160 mm, above the 5 mm base ring.
    pedestal.vertices[:,0:2]*=np.where(pedestal.vertices[:,2]>0,160/171,1)[:,None]
    pedestal.apply_translation([0,25,157.5])
    base=trimesh.creation.annulus(r_min=83.5,r_max=87,height=5,sections=24)
    base.apply_translation([0,25,132.5])
    return [('monitor-vents',vents,'black'),('stand',pedestal,'paint'),('stand-ring',base,'black')]


def tube_back(profile=None):
    """Opaque rear face of the source CRT, behind the curved front glass.

    The tube remains opaque when seen past its rounded front edge.
    """
    profile=profile or {}
    size=profile.get('size',[258,211]);position=profile.get('position',[0,-140,324])
    points=outline(*size,power=profile.get('outlinePower',4.5))*1.002
    edge=ring(points,position[1]+profile.get('backThickness',2),position[2])
    return surface([edge],center=[0,edge[0,1],position[2]])


def joint():
    """Recessed rounded dark lip behind the two-millimetre shell split."""
    xy=rounded(319,333,9.5);n=len(xy)
    vertices=[(x,y+25,z) for z in (318,322) for x,y in xy]
    vertices.extend([(0,25,318),(0,25,322)])
    faces=[]
    for i in range(n):
        j=(i+1)%n
        faces.extend([(i,j,j+n),(i,j+n,i+n),(2*n,j,i),(2*n+1,i+n,j+n)])
    return trimesh.Trimesh(vertices,faces,process=True)
