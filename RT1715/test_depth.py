"""Exercise the exact rasterizer on the host with an in-memory EMS/VGA backend."""
import ctypes
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

class Vertex(ctypes.Structure):
    _fields_=[(n,ctypes.c_long) for n in ('x','y','z','c')]

@unittest.skipUnless(shutil.which('cc'),'Host C compiler required')
class DepthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        lib=Path(cls.tmp.name)/'depth.so'
        subprocess.run(['cc','-shared','-fPIC','-DRT_HOST_TEST','-O2',str(Path(__file__).with_name('depth.c')),'-o',str(lib)],check=True)
        cls.lib=ctypes.CDLL(str(lib));cls.lib.rt_raster.argtypes=[ctypes.POINTER(Vertex),ctypes.c_int,ctypes.c_int]
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def setUp(self):
        self.lib.rt_depth_window(0,320,0,200);self.lib.rt_depth_begin()
    def draw(self,points,color,decal=0):
        v=(Vertex*len(points))(*(Vertex(x,y,z,color) for x,y,z in points))
        self.lib.rt_raster(v,len(points),decal)
    def test_intersecting_depth_planes_are_order_independent(self):
        a=[(20,20,1000),(300,20,4000),(300,180,4000),(20,180,1000)]
        b=[(20,20,4000),(300,20,1000),(300,180,1000),(20,180,4000)]
        for reverse in (False,True):
            self.lib.rt_depth_begin()
            for p,c in ([(b,50),(a,80)] if reverse else [(a,80),(b,50)]):self.draw(p,c)
            self.assertEqual(self.lib.rt_color_at(40,100),50)
            self.assertEqual(self.lib.rt_color_at(280,100),80)
    def test_screen_clipping_and_ems_page_boundaries(self):
        self.draw([(-100,-100,3000),(500,-100,3000),(500,400,3000),(-100,400,3000)],70)
        for y in (0,25,26,51,102,153,199):
            for x in (0,1,159,319):
                self.assertEqual(self.lib.rt_color_at(x,y),70)
                self.assertEqual(self.lib.rt_depth_at(x,y),3000)
    def test_near_surface_and_decal_survive_later_background(self):
        p=[(30,30,2000),(100,30,2000),(100,100,2000),(30,100,2000)]
        self.draw(p,60);self.draw(p,96,1);self.draw(p,60)
        self.assertEqual(self.lib.rt_color_at(50,50),96)
        self.draw([(0,0,1000),(320,0,1000),(320,200,1000),(0,200,1000)],40)
        self.assertEqual(self.lib.rt_color_at(50,50),96)
        self.assertEqual(self.lib.rt_color_at(150,150),40)

    def test_letterboxed_viewport_keeps_outer_rows_clear(self):
        self.lib.rt_depth_window(0,320,25,175)
        self.draw([(0,0,2000),(320,0,2000),(320,200,2000),(0,200,2000)],50)
        self.assertEqual(self.lib.rt_color_at(100,24),255)
        self.assertEqual(self.lib.rt_color_at(100,25),50)
        self.assertEqual(self.lib.rt_color_at(100,174),50)
        self.assertEqual(self.lib.rt_color_at(100,175),255)

    def test_clipped_edges_do_not_depend_on_traversal_direction(self):
        points=[(-73,13,2000),(367,47,2000),(137,227,2000)]
        self.draw(points,70)
        forward=[self.lib.rt_color_at(x,y) for y in range(200) for x in range(320)]
        self.lib.rt_depth_begin();self.draw(list(reversed(points)),70)
        backward=[self.lib.rt_color_at(x,y) for y in range(200) for x in range(320)]
        self.assertEqual(forward,backward)
