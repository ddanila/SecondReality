import unittest
from route_cache import compose, outside, signed, fnv

class RouteCacheTests(unittest.TestCase):
    def test_fixed_point_composition_translation_and_wrap(self):
        identity=[0,0,0,16384,0,0,0,16384,0,0,0,16384]
        local=[-123,456,789,*identity[3:]]
        self.assertEqual(compose(identity,local),local)
        camera=[-7,13,-29,*identity[3:]]
        self.assertEqual(compose(camera,local)[:3],[-130,469,760])
        self.assertEqual(signed(0xffffffff),-1)
        self.assertEqual(signed(65535,16),-1)
        # Integer matrix accumulation wraps before its arithmetic right shift.
        large=[0,0,0,*([32767]*9)]
        self.assertEqual(compose(large,large)[3],signed(3*32767**2)>>14)

    def test_bounds_keep_near_plane_and_viewport_margin(self):
        identity=[0,0,0,16384,0,0,0,16384,0,0,0,16384]
        self.assertFalse(outside([(-10,10),(-10,10),(511,513)],identity,250,220))
        self.assertTrue(outside([(-10,10),(-10,10),(0,511)],identity,250,220))
        self.assertTrue(outside([(10000,11000),(-10,10),(512,1024)],identity,250,220))
        self.assertFalse(outside([(-10,10),(-10,10),(512,1024)],identity,250,220))

    def test_asset_fingerprint_is_incremental_and_content_sensitive(self):
        self.assertEqual(fnv(b'abc'),fnv(b'bc',fnv(b'a')))
        self.assertNotEqual(fnv(b'abc'),fnv(b'abd'))
