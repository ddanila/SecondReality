"""Visible key silhouettes and ink must survive the DOS conversion."""
import unittest
import numpy as np
import trimesh
import keycaps
import robotron
import scene


class SourceKeyTests(unittest.TestCase):
    def cap(self,stretch=1):
        # Square skirt and narrow round body: same bounds as a generic tapered
        # block, but a very different silhouette above the shoulder.
        base=trimesh.creation.box(extents=[18,18,5.7]);base.apply_translation([0,0,2.85])
        body=trimesh.creation.cylinder(radius=7.2,height=5.7,sections=32)
        body.apply_translation([0,0,8.55])
        center=(np.linalg.norm(body.vertices[:,:2],axis=1)<.01)&(body.vertices[:,2]>11)
        body.vertices[center,2]-=.35
        source=trimesh.util.concatenate([base,body]);source.vertices[:,0]*=stretch
        return source

    def test_source_shoulder_round_body_and_closed_envelope(self):
        for stretch in (1,4):
            source=self.cap(stretch);cap=keycaps.detailed(source)
            self.assertTrue(cap.is_watertight)
            self.assertTrue(cap.is_winding_consistent)
            self.assertGreater(cap.volume,0)
            for z in (2,6,9):
                for angle in np.linspace(0,2*np.pi,17):
                    direction=np.array([np.cos(angle)*stretch,np.sin(angle),0.]);direction/=np.linalg.norm(direction)
                    original=max(keycaps.hits(source,np.array([0,0,z]),direction))
                    sampled=max(keycaps.hits(cap,np.array([0,0,z]),direction))
                    self.assertLess(abs(original-sampled),.65*stretch)
            # Full width at the skirt, narrower at the round body.
            self.assertLess(max(keycaps.hits(cap,np.array([0,0,7]),np.array([1.,0,0]))),8*stretch)
            binary=scene.encode('key-test',robotron.polygons(cap),96,16,precomputed_orders=False)
            self.assertLess(len(scene.decode(binary)['vertices']),500)

    def test_legends_follow_rendered_surface(self):
        cap=keycaps.detailed(self.cap())
        ink=keycaps.surface_legends(['!', '1'],cap,64)
        self.assertTrue(ink)
        self.assertGreater(np.ptp([p[2] for face in ink for p in face]),1)
        for face in ink:
            for x,y,z in face:
                clearance=z/64-keycaps.height(cap,x/64,y/64)
                self.assertGreater(clearance,0)
                self.assertLess(clearance,.06)

    def test_rounded_coarse_prefix_matches_renderer_contract(self):
        for stretch in (1,4):
            cap=keycaps.detailed(self.cap(stretch))
            coarse=keycaps.coarse_polygons(cap,64)
            self.assertEqual(len(coarse),14)
            data=scene.decode(scene.encode('"key-r-test"',coarse+robotron.polygons(cap),32,16,precomputed_orders=False))
            prefix=data['faces'][:14]
            self.assertEqual({i for f in prefix for i in f['indices']},set(range(16)))
            self.assertTrue(all(len(f['indices'])==4 for f in prefix))
            # The upper diagonal corners must follow the round body, rather
            # than becoming square corners of a tapered bounding box.
            top=np.array([p for f in coarse[3:6] for p in f])/64
            radius=np.linalg.norm(top[:,:2]/[stretch,1],axis=1)
            self.assertLess(max(radius),7.3)
            self.assertGreater(min(radius),6.9)
