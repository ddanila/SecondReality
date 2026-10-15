import json
import unittest
import numpy as np
import robotron
import scene


class KeyChannelTests(unittest.TestCase):
    def setUp(self):
        self.flight=json.loads((robotron.HERE/'assets/robotron/flight.json').read_text())

    def test_miniature_drone_fits_between_key_tops(self):
        source=scene.decode((robotron.HERE.parent/'MAIN/DATA/U2E.028').read_bytes())
        center=np.mean(source['bounds'],axis=1)
        vertices=np.array(source['vertices'])-center
        angle=np.radians(5.03193);c,s=np.cos(angle),np.sin(angle)
        keyboard=np.array([[1,0,0],[0,c,-s],[0,s,c]])
        for t in np.linspace(0,10,140):
            position=robotron.sample_track(self.flight['drone'],t,'position')
            points=vertices @ robotron.drone_rotation(self.flight,t).T/96*robotron.drone_scale(self.flight,t)+position
            local=(points-[0,-355,30.8244]) @ keyboard
            # Rounded bodies have at most 7.5 mm half-depth here. Adjacent
            # row centres are -35 and -16; even the wing tips must fit.
            if local[:,2].min()<11.4:
                self.assertGreater(local[:,1].min(),-35+7.5)
                self.assertLess(local[:,1].max(),-16-7.5)
            self.assertGreater(local[:,2].min(),6.4)
            if t<=7:self.assertLess(local[:,2].max(),11.4)
            eye=robotron.sample(self.flight,t)[0]
            eye_local=(eye-[0,-355,30.8244]) @ keyboard
            self.assertGreater(eye_local[2],11.4)

    def test_heading_leads_turn_and_swoosh_has_no_anticipation(self):
        f=self.flight;t=19
        def tangent(time):
            v=robotron.sample_track(f['drone'],time+.05,'position')-robotron.sample_track(f['drone'],time-.05,'position')
            return v/np.linalg.norm(v)
        heading=robotron.drone_rotation(f,t)[:,0]
        self.assertGreater(np.dot(heading,tangent(t+.45)),np.dot(heading,tangent(t))+.0001)
        for t in np.linspace(45,58,40):
            self.assertEqual(robotron.steering_time(f,t),t)
            self.assertEqual(robotron.drone_scale(f,t),1)
        scales=[robotron.drone_scale(f,t) for t in np.linspace(0,19,100)]
        self.assertGreaterEqual(min(np.diff(scales)),-1e-12)
        self.assertAlmostEqual(scales[0],.23)
        self.assertAlmostEqual(scales[-1],1.)
