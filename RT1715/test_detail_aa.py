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
        self.lib.rt_detail_opacity(255)
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
    def test_quarter_pixel_stroke_survives_pan(self):
        energies=[]
        for offset in range(16):
            self.setUp();self.draw(160+offset,164+offset);self.lib.rt_depth_flush()
            energies.append(sum(self.lib.rt_color_at(x,15) for x in range(9,13)))
        self.assertGreater(min(energies),12)
        self.assertLessEqual(max(energies)-min(energies),2)

    def test_sloping_surface_does_not_occlude_its_own_ink(self):
        for slope in (4,16,64,-4,-16,-64):
            self.setUp()
            self.lib.rt_raster((Vertex*4)(
                Vertex(0,0,2000,0),Vertex(20,0,2000+slope*20,0),
                Vertex(20,30,2000+slope*20,0),Vertex(0,30,2000,0)),4,0)
            left=2000+slope*10;right=left+slope//4
            self.lib.rt_detail_raster((Vertex*4)(
                Vertex(160,160,left,63),Vertex(164,160,right,63),
                Vertex(164,320,right,63),Vertex(160,320,left,63)),4)
            self.lib.rt_depth_flush()
            self.assertTrue(13<=self.lib.rt_color_at(10,15)<=17,slope)

    def test_integer_surface_projection_does_not_hide_subpixel_ink(self):
        # Same sloping surface, but its opaque projected vertices have lost
        # the fractional pixel retained by the ink. Test every Q4 phase.
        for slope in (4,16,64,-4,-16,-64):
            for phase in range(16):
                self.setUp()
                shift=slope*phase//16
                self.lib.rt_raster((Vertex*4)(
                    Vertex(0,0,2000+shift,0),Vertex(20,0,2000+shift+slope*20,0),
                    Vertex(20,30,2000+shift+slope*20,0),Vertex(0,30,2000+shift,0)),4,0)
                left=2000+slope*10;right=left+slope//4
                self.lib.rt_detail_raster((Vertex*4)(
                    Vertex(160,160,left,63),Vertex(164,160,right,63),
                    Vertex(164,320,right,63),Vertex(160,320,left,63)),4)
                self.lib.rt_depth_flush()
                self.assertTrue(13<=self.lib.rt_color_at(10,15)<=17,(slope,phase))

    def test_legend_fade_composites_without_a_hard_cut(self):
        samples=[]
        for opacity in (0,64,128,192,255):
            self.setUp();self.lib.rt_detail_opacity(opacity)
            self.draw(160,192);self.lib.rt_depth_flush()
            samples.append(self.lib.rt_color_at(10,15))
        self.assertEqual(samples[0],0)
        self.assertEqual(samples[-1],63)
        self.assertTrue(all(a<b for a,b in zip(samples,samples[1:])))
        self.assertTrue(29<=samples[2]<=33)

    def test_clipping_and_frame_reset(self):
        self.draw(-160,16);self.lib.rt_depth_flush();self.assertEqual(self.lib.rt_color_at(0,15),63)
        self.setUp();self.lib.rt_depth_flush();self.assertEqual(self.lib.rt_color_at(0,15),0)
