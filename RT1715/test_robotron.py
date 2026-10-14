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
