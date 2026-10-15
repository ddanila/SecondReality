"""Source-profile constraints for the close DOS monitor pass."""
import unittest
import numpy as np
import monitor_geometry as monitor
import robotron
import scene


class MonitorGeometryTests(unittest.TestCase):
    def test_glass_is_on_source_ellipsoid_and_inside_rounded_outline(self):
        glass,_=monitor.crt_surround()
        x,y,z=glass.vertices.T;z=z-324;depth=-140-y
        np.testing.assert_allclose((x/700)**2+(z/650)**2+((depth-18+600)/600)**2,1,atol=1e-12)
        self.assertLessEqual(np.max(abs(x/129)**4.5+abs(z/105.5)**4.5),1+1e-12)
        # The old rectangular corner is outside the tube's actual outline.
        self.assertFalse(np.any((abs(x)>128)&(abs(z)>105)))
        self.assertAlmostEqual(min(y),-158)

    def test_source_profile_is_used_instead_of_hardcoded_glass(self):
        glass,_=monitor.crt_surround({'size':[240,200],'outlinePower':4,'depth':16,'radii':[700,650,600],'position':[0,-140,324]})
        self.assertAlmostEqual(glass.extents[0],240)
        self.assertAlmostEqual(glass.extents[2],200)
        self.assertAlmostEqual(glass.bounds[0,1],-156)

    def test_smooth_glass_and_surround_fit_runtime_limits(self):
        for name,m in zip(['screen','rim'],monitor.crt_surround()):
            encoded=scene.encode(name,robotron.polygons(m),64,16,precomputed_orders=False,smooth=name=='screen')
            decoded=scene.decode(encoded)
            self.assertLessEqual(len(decoded['vertices']),500)
            self.assertLessEqual(len(decoded['faces']),500)

    def test_front_gasket_is_half_a_millimetre(self):
        glass,gasket=monitor.crt_surround()
        self.assertAlmostEqual(gasket.extents[0]-glass.extents[0],1)
        self.assertAlmostEqual(gasket.extents[2]-glass.extents[2],1)

    def test_bezel_has_closed_outer_return_to_housing(self):
        bezel=monitor.bezel();bezel.merge_vertices()
        self.assertTrue(bezel.is_winding_consistent)
        edges=bezel.edges_unique[np.bincount(bezel.edges_unique_inverse)==1]
        # Only the glass opening and the shared housing rim remain open.
        self.assertTrue(np.allclose(bezel.vertices[edges][:,:,1],-142))
        self.assertEqual(len(edges),36)

    def test_shell_has_rounded_corners_and_source_envelope(self):
        shell=monitor.housing()
        np.testing.assert_allclose(shell.bounds,[[-160,-142,180],[160,192,460]],atol=.01)
        # No point reaches the sharp box corner; source uses 10 mm bends.
        self.assertFalse(np.any((shell.vertices[:,0]>159.9)&(shell.vertices[:,2]>459.9)))
        triangles=shell.triangles
        self.assertFalse(np.any((triangles[:,:,2].min(axis=1)<320)&(triangles[:,:,2].max(axis=1)>320)))
