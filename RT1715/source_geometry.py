"""Preserve canonical front-panel openings and mouldings in DOS mesh chunks."""
import numpy as np
import trimesh


def chunks(source, faces_per_chunk=120, precision=(.5,.1,.5)):
    source=source.copy()
    # Collapse sub-pixel tessellation of rounded mouldings, retaining the real
    # openings and recesses. 0.5 mm in X/Z, 0.1 mm through the thin front skin.
    source.vertices=np.round(source.vertices/precision)*precision
    source.merge_vertices()
    source.update_faces(source.nondegenerate_faces())
    source.update_faces(source.unique_faces())
    source.remove_unreferenced_vertices()
    # Spatially adjacent triangles share vertices, reducing conventional RAM.
    centers=source.triangles_center
    order=np.lexsort((centers[:,2],centers[:,1],centers[:,0]))
    for start in range(0,len(order),faces_per_chunk):
        yield source.submesh([order[start:start+faces_per_chunk]],append=True)


def front_parts(load, records):
    definitions=[('fascia','paint'),('drives','dark'),('drive-insets','dark'),
                 ('drive-latch-0','black'),('drive-latch-1','black'),
                 ('drive-led-0','red'),('drive-led-1','red'),
                 ('drive-direction-0','white'),('drive-direction-1','white'),
                 ('reset','dark'),('power','white'),('power-housing','black')]
    for name,color in definitions:
        source=load(records[name])
        if name=='power':
            # Preserve the recessed lens envelope; its sub-millimetre texture
            # alone contains thousands of triangles and is below VGA resolution.
            from robotron_lod import box
            source=box(*source.bounds)
        # Interior-facing backs of these opaque front mouldings are hidden.
        source=source.submesh([np.flatnonzero(source.face_normals[:,1]<.5)],append=True)
        precision=(.2,.1,.2) if name.startswith('drive-latch') else (.5,.1,.5)
        for index,part in enumerate(chunks(source,precision=precision)):
            yield f'src-{name}-{index}',part,color,'exterior'
    source=load(records['case-base'])
    # Original bottom skin and side/rear vents stay in the lightweight shell;
    # retain the current source's complete front face and control apertures.
    selected=np.all(source.triangles[:,:,1]<-195,axis=1)
    selected &= source.face_normals[:,1]<.9
    front=source.submesh([np.flatnonzero(selected)],append=True)
    for index,part in enumerate(chunks(front)):
        yield f'src-base-front-{index}',part,'paint','exterior'
