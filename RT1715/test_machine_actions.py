"""Sequence order, rigid mechanical motion and clearance on the authored route."""
import json
import unittest
import numpy as np
import robotron
import machine_actions as machine
import scene


class MachineActionTests(unittest.TestCase):
    def setUp(self):
        self.flight=json.loads((robotron.HERE/'assets/robotron/flight.json').read_text())
        self.settings=self.flight['machine']
        self.data={'driveMotion':[{'unit':0,'latchPivot':[-113,-211,92]}]}
        self.base=(0,0,0,*machine.IDENTITY)

    def test_disk_seats_before_lever_closes_and_boot_starts(self):
        s=self.settings
        self.assertLess(s['insert'][1],s['close'][0])
        self.assertGreater(min(line['time'] for line in s['boot_frames']),s['close'][1])
        values=[machine.pose('disk-jacket',self.base,t,s,self.data)[1] for t in np.linspace(0,58,200)]
        self.assertEqual(values[0],-90*64)
        self.assertEqual(values[-1],0)
        self.assertTrue(np.all(np.diff(values)>=0))

    def test_latch_keeps_its_raised_pivot_and_turns_down(self):
        pivot=np.array([-113,-211,92])*64
        for t in np.linspace(0,30,80):
            pose=machine.pose('src-drive-latch-0-0',self.base,t,self.settings,self.data)
            r=np.array(pose[3:]).reshape(3,3)/16384
            np.testing.assert_allclose(r@pivot+pose[:3],pivot+[0,0,6*64],atol=1)
            np.testing.assert_allclose(r.T@r,np.eye(3),atol=.0001)
        np.testing.assert_allclose(r@[30,0,0],[0,0,-30],atol=.001)
        opened=machine.pose('src-drive-latch-0-0',self.base,26,self.settings,self.data)
        r=np.array(opened[3:]).reshape(3,3)/16384
        np.testing.assert_allclose(r@[30,0,0],[30,0,0],atol=.001)
        # Entire hub and raised handle stay above the highest disk label point.
        # Source hub radius 6.5 mm; finger outline reaches 6 mm either side.
        hub=np.array([[dx,0,dz] for dx,dz in [(6.5,0),(-6.5,0),(0,6.5),(0,-6.5)]])+pivot/64
        raised=hub@r.T+np.array(opened[:3])/64
        self.assertGreater(raised[:,2].min(),90.301)
        self.assertEqual(machine.pose('src-drive-latch-1-0',self.base,30,self.settings,self.data),self.base)

    def test_disk_is_clear_of_drone_during_loading(self):
        drone=scene.decode((robotron.HERE.parent/'MAIN/DATA/U2E.028').read_bytes())
        vertices=np.array(drone['vertices'])-np.mean(drone['bounds'],axis=1)
        for t in np.linspace(24,29,201):
            p=robotron.sample_track(self.flight['drone'],t,'position')
            points=vertices@robotron.drone_rotation(self.flight,t).T/96+p
            shift=machine.pose('disk-jacket',self.base,t,self.settings,self.data)[1]/64
            lo=np.array([-227.676,-203.676+shift,89]);hi=np.array([-94.324,-70.324+shift,90.301])
            self.assertTrue(np.any(points.max(axis=0)<lo) or np.any(points.min(axis=0)>hi),f'drone/disk overlap at {t}')

    def test_boot_visibility_is_time_driven_and_cursor_blinks(self):
        s=self.settings
        self.assertFalse(machine.visible('boot-0-0',29,s))
        self.assertTrue(machine.visible('boot-0-0',32,s))
        self.assertTrue(machine.visible('boot-2-0',38,s))
        self.assertFalse(machine.visible('boot-2-0',39,s))
        self.assertTrue(machine.visible('boot-3-0',39,s))
        self.assertTrue(machine.visible('boot-4-0',39.1,s))
        self.assertFalse(machine.visible('boot-4-0',39.6,s))
        self.assertFalse(machine.visible('disk-jacket',30,s))
        self.assertFalse(machine.visible('boot-led',39,s))

    def test_boot_masks_match_recorded_capture_hashes(self):
        import hashlib
        from PIL import Image
        provenance=json.loads((machine.BOOT/'provenance.json').read_text())
        for name,digest in provenance['assets'].items():
            self.assertEqual(hashlib.sha256((machine.BOOT/name).read_bytes()).hexdigest(),digest)
        with Image.open(machine.BOOT/'cursor.png') as cursor:
            self.assertEqual(cursor.getbbox(),(16,48,24,60))
        with Image.open(machine.BOOT/'prompt.png') as prompt:
            self.assertIsNotNone(prompt.crop((0,48,16,60)).getbbox())
            self.assertIsNone(prompt.crop((16,48,24,60)).getbbox())
