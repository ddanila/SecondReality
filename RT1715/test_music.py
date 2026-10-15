import json
from pathlib import Path
import unittest

from music import timeline
from prepare import printable

HERE = Path(__file__).resolve().parent


class MusicTimingTests(unittest.TestCase):
    def test_released_soundtrack_cues_include_breaks_and_speed_changes(self):
        rows = timeline(HERE.parent/'MAIN/MUSIC0.S3M')
        by_pos = {(r['order'],r['row']):r for r in rows}
        self.assertAlmostEqual(by_pos[19,0]['seconds'],3.84)
        self.assertAlmostEqual(by_pos[25,6]['seconds'],51.60)
        self.assertAlmostEqual(by_pos[25,8]['seconds'],51.84)
        self.assertAlmostEqual(by_pos[28,0]['seconds'],62.40)
        self.assertTrue(any(e.get('instrument')==23 for e in by_pos[25,6]['events']))
        self.assertNotIn((18,32),by_pos)
        self.assertNotIn((26,62),by_pos)
        self.assertNotIn((27,0),by_pos)

    def test_drone_pass_and_reveal_follow_soundtrack(self):
        import numpy as np
        import robotron
        f=json.loads((HERE/'assets/robotron/flight.json').read_text())
        t=51.60-3.84
        eye,target=robotron.sample(f,t)
        drone=robotron.sample_track(f['drone'],t,'position')
        camera=np.array(robotron.camera(eye,target)[3:]).reshape(3,3)/16384
        x,y,z=camera @ (drone-eye)
        self.assertGreater(z,8)
        self.assertLess(z,100)
        self.assertLess(abs(x/z),.2)
        self.assertLess(abs(y/z),.3)
        self.assertGreater(np.linalg.norm(robotron.sample(f,48.1)[0]),1200)
        self.assertGreater(np.linalg.norm(eye),1200)
        self.assertLess(f['frames']/f['fps'],62.40-3.84)

    def test_original_credit_count_and_ascii_specs(self):
        cards=json.loads((HERE/'assets/robotron/credits.json').read_text())
        self.assertEqual(len(cards),21)
        for card in cards:
            printable(card['lines'])
        text=' '.join(line for c in cards for line in c['lines'])
        for value in ('256 KiB','U8272','UA858','UL6516D','reference'):
            self.assertIn(value,text)

    def test_runtime_trace_rejects_truncated_flight_and_late_credits(self):
        from run import verify_sync
        flight = ("SWOOSH frame=3344 order=25 row=6\n"
                  "OVERVIEW frame=3186 order=24 row=54\n"
                  "END order=26 row=57 frame=4064\n")
        credits = "START order=28 row=0\nEND order=43 row=46\nCOMPLETE\n"
        self.assertEqual(verify_sync(flight, credits)['credits_start'], (28,0))
        with self.assertRaises(ValueError):
            verify_sync(flight.replace('END order=26 row=57','END order=19 row=4'),credits)
        with self.assertRaises(ValueError):
            verify_sync(flight,credits.replace('START order=28 row=0','START order=28 row=10'))

    def test_wide_camera_and_straight_drone_exit_cover_the_swoosh(self):
        import numpy as np
        import robotron
        f=json.loads((HERE/'assets/robotron/flight.json').read_text())
        eye,target=robotron.sample(f,47.76)
        camera=np.array(robotron.camera(eye,target)[3:]).reshape(3,3)/16384
        direction=np.linalg.solve(camera,[240.,-160.,-20.]);direction/=np.linalg.norm(direction)
        for t in np.linspace(45.5,48.5,60):
            np.testing.assert_allclose(robotron.sample(f,t)[0],eye,atol=1e-8)
        for t in np.linspace(47.1,48.1,50):
            heading=robotron.drone_rotation(f,t) @ [1.,0.,0.]
            self.assertGreater(np.dot(heading,direction),.99999)
        before=camera @ (robotron.sample_track(f['drone'],47.5,'position')-eye)
        after=camera @ (robotron.sample_track(f['drone'],48,'position')-eye)
        self.assertLess(before[0],0);self.assertGreater(before[1],0)
        self.assertGreater(after[0],0);self.assertLess(after[1],0)
        self.assertGreater(after[2],40)

    def test_credit_views_are_unique_and_focus_memory_on_its_chips(self):
        cards=json.loads((HERE/'assets/robotron/credits.json').read_text())
        self.assertEqual(len({c['image'] for c in cards}),21)
        views={c['image']:c['view'] for c in cards}
        self.assertEqual(views['display-ram']['focus_chips'],['UL6516D'])
        self.assertEqual(views['main-ram']['focus_chips'],['M4164B'])
        self.assertIn('keyboard-controller-rom-cover',views['keyboard-rom']['focus_parts'])

    def test_diagonal_approach_accelerates_into_the_swoosh(self):
        import numpy as np
        import robotron
        f=json.loads((HERE/'assets/robotron/flight.json').read_text())
        def speed(t):
            return np.linalg.norm(robotron.sample_track(f['drone'],t+.01,'position')-
                                  robotron.sample_track(f['drone'],t-.01,'position'))/.02
        self.assertGreater(speed(47.9),speed(47.2)*1.4)
