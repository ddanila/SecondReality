"""Filtered markings retain subpixel coverage and respect opaque depth."""
import ctypes
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from detail_palette import lookup
from test_depth import Vertex


@unittest.skipUnless(shutil.which('cc'),'Host C compiler required')
class DetailTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();path=Path(cls.tmp.name)/'detail.so'
        subprocess.run(['cc','-shared','-fPIC','-O2','-DRT_HOST_TEST',str(Path(__file__).with_name('depth.c')),'-o',str(path)],check=True)
        cls.lib=ctypes.CDLL(str(path));cls.lib.rt_raster.argtypes=[ctypes.POINTER(Vertex),ctypes.c_int,ctypes.c_int]
        cls.lib.rt_detail_raster.argtypes=[ctypes.POINTER(Vertex),ctypes.c_int]
        palette=bytes(v for i in range(256) for v in [min(i,63)]*3)
        cls.palette=ctypes.create_string_buffer(palette);cls.table=ctypes.create_string_buffer(lookup(palette))
        cls.lib.rt_detail_init(cls.palette,cls.table)
    @classmethod
    def tearDownClass(cls):cls.lib.rt_depth_end();cls.tmp.cleanup()
    def setUp(self):
        self.lib.rt_depth_window(0,320,0,200);self.lib.rt_depth_begin()
        self.lib.rt_raster((Vertex*4)(Vertex(0,0,1000,0),Vertex(320,0,1000,0),Vertex(320,200,1000,0),Vertex(0,200,1000,0)),4,0)
    def draw(self,x0,x1,z=1100):
        self.lib.rt_detail_raster((Vertex*4)(Vertex(x0,160,z,63),Vertex(x1,160,z,63),Vertex(x1,320,z,63),Vertex(x0,320,z,63)),4)
    def test_half_pixel_stroke_blends_instead_of_disappearing(self):
        self.draw(160,168);self.lib.rt_depth_flush()
        self.assertTrue(29<=self.lib.rt_color_at(10,15)<=33)
        self.assertEqual(self.lib.rt_color_at(11,15),0)
    def test_later_opaque_surface_occludes_deferred_ink(self):
        self.draw(160,192)
        self.lib.rt_raster((Vertex*4)(Vertex(0,0,2000,20),Vertex(20,0,2000,20),Vertex(20,30,2000,20),Vertex(0,30,2000,20)),4,0)
        self.lib.rt_depth_flush();self.assertEqual(self.lib.rt_color_at(10,15),20)
    def test_subpixel_pan_preserves_stroke_energy(self):
        energies=[]
        for offset in range(0,16,4):
            self.setUp();self.draw(160+offset,168+offset);self.lib.rt_depth_flush()
            energies.append(sum(self.lib.rt_color_at(x,15) for x in range(9,13)))
        self.assertLessEqual(max(energies)-min(energies),2)
    def test_clipping_and_frame_reset(self):
        self.draw(-160,16);self.lib.rt_depth_flush();self.assertEqual(self.lib.rt_color_at(0,15),63)
        self.setUp();self.lib.rt_depth_flush();self.assertEqual(self.lib.rt_color_at(0,15),0)
