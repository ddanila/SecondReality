"""Check visibility rewriting against the released animation data."""
import unittest

import animation
from prepare import ORIGINAL


class AnimationTests(unittest.TestCase):
    def setUp(self):
        self.data = (ORIGINAL/'U2E.0AB').read_bytes()
        self.meshes = animation.mapping((ORIGINAL/'U2E.00M').read_bytes())

    def test_static_visibility_preserves_camera_motion_and_frame_timing(self):
        original = animation.decode(self.data,len(self.meshes))
        output, report = animation.static_visibility(self.data,self.meshes)
        rewritten = animation.decode(output,len(self.meshes))
        self.assertEqual(len(original),1801)
        self.assertEqual(len(rewritten),len(original))
        static = set(report['always_visible_objects'])
        self.assertEqual(len(static),51)
        self.assertEqual(report['preserved_objects'],[2,28,35,51,52,57])
        poses = {}
        for before,after in zip(original,rewritten):
            self.assertEqual(before[1],after[1])
            self.assertEqual([r for r in before[0] if r['object'] not in static],
                             [r for r in after[0] if r['object'] not in static])
            for r in after[0]:
                if r['object'] in static:
                    self.assertTrue(r['visible'])
                    poses[r['object']] = r['state']
            for r in before[0]:
                if r['object'] in static and r['visible']:
                    self.assertEqual(r['state'],poses[r['object']])
        self.assertEqual(set(poses),static)

    def test_truncated_stream_and_invalid_object_rejected(self):
        for data in (self.data[:-1],self.data+b'junk',b'\xc3\x0f\xff\xff'):
            with self.assertRaises(ValueError):
                animation.decode(data,len(self.meshes))


if __name__ == '__main__':
    unittest.main()
