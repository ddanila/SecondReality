"""Camera and complete-track tests for the optional Robotron toolchain."""
import unittest
try:
    import robotron
except ImportError:
    robotron = None
import animation


@unittest.skipIf(robotron is None, 'Install requirements-robotron.txt')
class RobotronTests(unittest.TestCase):
    def test_camera_looks_forward_with_screen_y_down(self):
        self.assertEqual(robotron.camera([0,0,0],[0,1,0]),
                         (0,0,0,16384,0,0,0,0,-16384,0,16384,0))
        pose=robotron.camera([10,20,30],[10,21,30])
        self.assertEqual(pose[:3],(-640,1920,-1280))

    def test_complete_tracks_keep_hidden_motion(self):
        a=(0,0,0,*robotron.IDENTITY)
        b=(200,-500,100000,-16000,0,0,0,-16000,0,0,0,16384)
        data=robotron.encode_animation([[a,a],[a,b],[b,a]],
                                      [[True,False],[True,False],[True,True]],52)
        frames=animation.decode(data,2)
        state=[None,None]
        for i,(records,fov) in enumerate(frames):
            for r in records: state[r['object']]=r['state']
            self.assertEqual(state,[[a,a],[a,b],[b,a]][i])
            self.assertEqual(fov,round(52*256/360))
        self.assertFalse(frames[1][0][0]['visible'])

    def test_coplanar_box_faces_merge_without_changing_bounds(self):
        import trimesh
        import scene
        quads=robotron.polygons(trimesh.creation.box(extents=[2,4,6]))
        self.assertEqual(len(quads),6)
        self.assertTrue(all(len(p)==4 for p in quads))
        mesh=scene.decode(scene.encode('box',quads))
        self.assertEqual(mesh['bounds'],[[-64,64],[-128,128],[-192,192]])

    def test_keyframe_endpoints(self):
        flight={'keyframes':[{'time':0,'eye':[0,0,0],'target':[1,1,1]},
                             {'time':1,'eye':[2,2,2],'target':[3,3,3]}]}
        for t,eye in ((0,[0,0,0]),(.5,[1,1,1]),(1,[2,2,2])):
            self.assertEqual(robotron.sample(flight,t)[0].tolist(),eye)

    def test_keycaps_are_closed_and_preserve_source_dimensions(self):
        import trimesh
        from robotron_lod import keycap
        for size in ([17.8,17.8,11.5],[112,17.8,11.5],[36,36,11.5]):
            original=trimesh.creation.box(extents=size)
            result=keycap(original)
            self.assertTrue(result.is_watertight)
            self.assertTrue(result.is_winding_consistent)
            self.assertEqual(result.bounds.tolist(),original.bounds.tolist())

    def test_scenic_tracks_are_continuous_and_drone_moves_in_camera_view(self):
        import json
        import numpy as np
        flight=json.loads((robotron.HERE/'assets/robotron/flight.json').read_text())
        projected=[]
        for t in np.linspace(0,43,200):
            eye,target=robotron.sample(flight,t)
            drone=robotron.sample_track(flight['drone'],t,'position')
            pose=robotron.camera(eye,target)
            v=np.array(pose[3:]).reshape(3,3)/16384 @ (drone-eye)
            self.assertGreater(v[2],8)
            projected.append(v[:2]/v[2])
        self.assertGreater(np.ptp(np.array(projected)[:,0]),.3)
        for key in flight['keyframes'][1:-1]:
            t=key['time'];epsilon=.001
            p0=robotron.sample(flight,t-epsilon)[0]
            p1=robotron.sample(flight,t)[0]
            p2=robotron.sample(flight,t+epsilon)[0]
            self.assertLess(np.linalg.norm((p2-p1)-(p1-p0)),.001)

    def test_drone_nose_tracks_full_3d_velocity_through_entire_flight(self):
        import json
        import numpy as np
        flight=json.loads((robotron.HERE/'assets/robotron/flight.json').read_text())
        end=flight['drone'][-1]['time']
        for t in np.linspace(0,end,500):
            lo=max(0,t-.05);hi=min(end,t+.05)
            tangent=robotron.sample_track(flight['drone'],hi,'position')-robotron.sample_track(flight['drone'],lo,'position')
            tangent/=np.linalg.norm(tangent)
            rotation=robotron.drone_rotation(flight,t)
            # +X is the nose of U2E.028. Banking must not change its heading.
            np.testing.assert_allclose(rotation @ [1.,0.,0.],tangent,atol=1e-10)
            np.testing.assert_allclose(rotation.T @ rotation,np.eye(3),atol=1e-10)
            self.assertAlmostEqual(np.linalg.det(rotation),1.)

    def test_crt_rim_covers_every_glass_boundary_vertex(self):
        import numpy as np
        from robotron_lod import crt_surround
        glass,rim=crt_surround()
        edges=glass.edges
        counts={}
        for a,b in edges:
            edge=tuple(sorted((a,b)));counts[edge]=counts.get(edge,0)+1
        boundary={v for edge,count in counts.items() if count==1 for v in edge}
        self.assertEqual(len(boundary),28)
        for v in glass.vertices[list(boundary)]:
            distance=np.linalg.norm(rim.vertices-v,axis=1)
            self.assertLess(distance.min(),.35)
        self.assertTrue(np.all(glass.face_normals[:,1]<0))
        self.assertTrue(np.all(rim.face_normals[:,1]<0))
