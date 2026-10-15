"""Camera pursuit and the post-swoosh rigid assembly turn."""
import json
import unittest
import numpy as np
import robotron

class CameraMotionTests(unittest.TestCase):
    def setUp(self):
        self.flight=json.loads((robotron.HERE/'assets/robotron/flight.json').read_text())

    def test_close_flyover_has_no_stops_and_smooth_acceleration(self):
        f=self.flight
        for t in np.linspace(.01,41.99,500):
            speed=np.linalg.norm((robotron.sample(f,t+.005)[0]-robotron.sample(f,t-.005)[0])/.01)
            self.assertGreater(speed,5, f'Camera stalls at {t}')
        def acceleration(t,component):
            h=.0001
            return (robotron.sample(f,t+h)[component]-2*robotron.sample(f,t)[component]+robotron.sample(f,t-h)[component])/(h*h)
        for t in [k['time'] for k in f['keyframes'][1:-1]]+[30,36]:
            for component in (0,1):
                left=2*acceleration(t-.0002,component)-acceleration(t-.0004,component)
                right=2*acceleration(t+.0002,component)-acceleration(t+.0004,component)
                np.testing.assert_allclose(left,right,atol=.03)

    def test_turn_is_counterclockwise_rigid_and_after_flyby(self):
        f=self.flight;pivot=np.array(f['turntable']['pivot'])*robotron.SCALE
        point=pivot+np.array([100,0,35])*robotron.SCALE
        pose=tuple(point)+tuple((np.eye(3)*16384).astype(int).flatten())
        self.assertEqual(robotron.assembly_pose(f,48.1,pose),pose)
        final=robotron.assembly_pose(f,58,pose)
        np.testing.assert_allclose(final[:3],pivot+np.array([0,100,35])*robotron.SCALE,atol=1)
        np.testing.assert_allclose(np.array(final[3:]).reshape(3,3) @ [1,0,0],[0,16384,0],atol=1)
        angles=[]
        for t in np.linspace(48.5,58,150):
            result=robotron.assembly_pose(f,t,pose);basis=np.array(result[3:]).reshape(3,3)/16384
            np.testing.assert_allclose(basis.T@basis,np.eye(3),atol=.0001)
            self.assertAlmostEqual(np.linalg.norm(np.array(result[:3])-pivot),np.linalg.norm(point-pivot),delta=1)
            angles.append(np.arctan2(basis[1,0],basis[0,0]))
        self.assertGreaterEqual(min(np.diff(angles)),-1e-9)

    def test_wide_camera_stays_fixed_through_swoosh_and_turn(self):
        expected=robotron.sample(self.flight,45.5)
        for t in np.linspace(45.5,58,80):
            for actual,want in zip(robotron.sample(self.flight,t),expected):np.testing.assert_allclose(actual,want,atol=1e-9)
