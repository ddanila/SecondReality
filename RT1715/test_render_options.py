"""Rendering experiments must preserve depth, ties, decals and viewport edges."""
import ctypes
import random
import unittest
import test_depth
Vertex=test_depth.Vertex

class RenderOptionTests(unittest.TestCase):
    setUpClass=classmethod(test_depth.DepthTests.setUpClass.__func__)
    tearDownClass=classmethod(test_depth.DepthTests.tearDownClass.__func__)
    setUp=test_depth.DepthTests.setUp
    draw=test_depth.DepthTests.draw
    def test_layers_match_reference_for_all_backends(self):
        rng=random.Random(1997)
        layers=[]
        # Occluding foreground, a hole, equal-depth ties, decals and gradients.
        for depth,color in ((8000,50),(1000,60),(8000,70)):
            layers.append(([(0,25,depth,color),(320,25,depth,color),(160,175,depth,color)],0))
        for i in range(80):
            layers.append(([(rng.randrange(-80,400),rng.randrange(-50,250),rng.randrange(1,65536),rng.randrange(256)) for _ in range(3)],i&1))
        flags=[ctypes.c_int.in_dll(self.lib,n) for n in ('rt_occlusion','rt_tiles','rt_visible_spans')]
        def render(mode):
            for i,flag in enumerate(flags):flag.value=(mode>>i)&1
            self.lib.rt_depth_window(0,320,25,175);self.lib.rt_depth_begin()
            for vertices,decal in layers:self.lib.rt_raster((Vertex*3)(*(Vertex(*v) for v in vertices)),3,decal)
            self.lib.rt_depth_flush()
            return [(self.lib.rt_depth_at(x,y),self.lib.rt_color_at(x,y)) for y in range(200) for x in range(320)]
        try:
            expected=render(0)
            for mode in range(1,8):self.assertEqual(render(mode),expected,f'backend {mode}')
        finally:
            for flag in flags:flag.value=0

    def test_occlusion_rejects_only_fully_covered_tiles(self):
        flag=ctypes.c_int.in_dll(self.lib,'rt_occlusion');counter=ctypes.c_ulong.in_dll(self.lib,'rt_occluded')
        try:
            flag.value=1;counter.value=0
            self.draw([(0,0,6000),(320,0,6000),(320,200,6000),(0,200,6000)],30)
            self.draw([(32,32,1000),(64,32,1000),(32,64,1000)],40)
            self.assertGreater(counter.value,0)
            self.assertEqual(self.lib.rt_color_at(40,40),30)
        finally:flag.value=0

    def test_bounded_queues_flush_without_losing_surfaces(self):
        flags=[ctypes.c_int.in_dll(self.lib,n) for n in ('rt_tiles','rt_visible_spans')]
        try:
            for mode in (1,2,3):
                for i,flag in enumerate(flags):flag.value=(mode>>i)&1
                self.lib.rt_depth_begin()
                for i in range(8193):
                    self.draw([(32,32,1000+i),(34,32,1000+i),(32,34,1000+i)],i%255)
                self.lib.rt_depth_flush()
                self.assertEqual(self.lib.rt_depth_at(32,32),9192)
                self.assertEqual(self.lib.rt_color_at(32,32),8192%255)
                self.assertEqual(self.lib.rt_color_at(40,40),255)
        finally:
            for flag in flags:flag.value=0
