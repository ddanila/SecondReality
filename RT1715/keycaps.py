"""Sample the visible envelope of canonical key meshes, omitting hidden cavities.

Horizontal sections retain the moulded skirt/shoulder; vertical rays retain the
actual dished top. No mesh decimator is allowed to collapse thin key shells.
"""
import numpy as np
import trimesh


def hits(mesh, origin, direction):
    """Positive ray intersections, without optional spatial-index dependencies."""
    triangles=mesh.triangles
    a=triangles[:,0];e1=triangles[:,1]-a;e2=triangles[:,2]-a
    h=np.cross(direction,e2);det=np.einsum('ij,ij->i',e1,h)
    valid=np.abs(det)>1e-10
    inv=np.zeros_like(det);inv[valid]=1/det[valid]
    s=origin-a;u=inv*np.einsum('ij,ij->i',s,h)
    q=np.cross(s,e1);v=inv*(q@direction);t=inv*np.einsum('ij,ij->i',e2,q)
    return t[valid & (u>=-1e-7) & (v>=-1e-7) & (u+v<=1+1e-7) & (t>=0)]


def height(mesh,x,y):
    ceiling=mesh.bounds[1,2]+1
    distances=hits(mesh,np.array([x,y,ceiling]),np.array([0.,0.,-1.]))
    if not len(distances):raise ValueError('Key surface sample misses source mesh')
    return ceiling-min(distances)


def detailed(source):
    lo,hi=source.bounds;center=(lo[:2]+hi[:2])/2;half=(hi[:2]-lo[:2])/2
    # The source's repeated horizontal levels describe the skirt and shoulder.
    # Keep its large steps; top curvature is sampled separately with vertical rays.
    z,counts=np.unique(np.round(source.vertices[:,2],4),return_counts=True)
    candidates=z[(counts>=24)&(z>max(0,lo[2])+.1)&(z<hi[2]-1)]
    levels=[max(0,float(lo[2])),*[float(v)+side*.001 for v in candidates for side in (-1,1)],float(hi[2]-.4)]
    rings=[];n=16
    for level in levels:
        ring=[]
        for angle in np.arange(n)*2*np.pi/n:
            direction=np.array([np.cos(angle)*half[0],np.sin(angle)*half[1],0.])
            direction/=np.linalg.norm(direction)
            origin=np.array([*center,level+1e-4])
            distances=hits(source,origin,direction)
            if not len(distances):raise ValueError('Key wall sample misses source mesh')
            point=origin+direction*max(distances);point[2]=level
            ring.append(point)
        rings.append(np.array(ring))
    # Remove levels belonging only to hidden cavities. Retain abrupt exterior
    # shoulders rather than replacing them with a bounding-box taper.
    while len(rings)>2:
        errors=[]
        for i in range(1,len(rings)-1):
            u=(levels[i]-levels[i-1])/(levels[i+1]-levels[i-1])
            estimate=rings[i-1]*(1-u)+rings[i+1]*u
            errors.append(float(np.max(np.linalg.norm(rings[i]-estimate,axis=1))))
        remove=int(np.argmin(errors))+1
        if min(errors)>.04 and len(rings)<=7:break
        del rings[remove];del levels[remove]
    vertices=list(np.concatenate(rings))
    faces=[]
    faces.extend((0,i+1,i) for i in range(1,n-1))
    for layer in range(len(levels)-1):
        for i in range(n):
            j=(i+1)%n;a=layer*n+i;b=layer*n+j
            faces.extend([(a,b,b+n),(a,b+n,a+n)])
    # Project the outer lip and inner dish onto the original surface.
    outer=len(vertices)-n
    for i in range(n):
        point=vertices[outer+i]
        point[2]=height(source,*point[:2])
    inner=len(vertices)
    for i in range(n):
        xy=center+(vertices[outer+i][:2]-center)*.65
        vertices.append(np.array([*xy,height(source,*xy)]))
    middle=len(vertices);vertices.append(np.array([*center,height(source,*center)]))
    for i in range(n):
        j=(i+1)%n
        faces.extend([(outer+i,outer+j,inner+j),(outer+i,inner+j,inner+i),(inner+i,inner+j,middle)])
    result=trimesh.Trimesh(vertices,faces,process=True)
    if not result.is_watertight or result.volume<=0:raise ValueError('Invalid sampled key envelope')
    return result


def surface_legends(lines,mesh,scale):
    import legends
    # Smaller, source-colour ink follows the rendered dish, not a floating plane.
    bounds=mesh.bounds.copy();bounds[0,:2]+=1;bounds[1,:2]-=1
    faces=legends.polygons(lines,bounds,scale)
    projected=[]
    for face in faces:
        points=[(x,y,round((height(mesh,x/scale,y/scale)+.045)*scale)) for x,y,_ in face]
        projected.extend([points[:3],[points[0],points[2],points[3]]])
    return projected
