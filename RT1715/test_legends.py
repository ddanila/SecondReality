"""Bitmap coverage and coplanar label geometry regression checks."""
import unittest
import legends
import scene


class LegendTests(unittest.TestCase):
    def test_rectangles_exactly_cover_glyph_pixels_without_overlap(self):
        for lines in [['A'],['PF10'],['!', '1'],list(legends.SYMBOLS),['ß','¤']]:
            im=legends.bitmap(lines)
            covered=set()
            for x0,y0,x1,y1 in legends.rectangles(im):
                rectangle={(x,y) for x in range(x0,x1) for y in range(y0,y1)}
                self.assertFalse(rectangle & covered)
                covered |= rectangle
            expected={(x,y) for x in range(im.width) for y in range(im.height) if im.getpixel((x,y))}
            self.assertEqual(covered,expected)
            self.assertTrue(covered)

    def test_legends_fit_flat_dish_and_keep_outward_winding(self):
        for lines in [['W'],['CTRL'],['PF10'],['?', 'ß'],['↵']]:
            faces=legends.polygons(lines,[[-8.9,-8.9,-2],[8.9,8.9,9.5]],64)
            for face in faces:
                for x,y,z in face:
                    self.assertLessEqual(abs(x),round(5.9*64))
                    self.assertLessEqual(abs(y),round(4.4*64))
                    self.assertEqual(z,round(8.66*64))
                a,b,c=face[:3]
                self.assertGreater((b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0]),0)
            scene.decode(scene.encode('legend',faces,96,16,precomputed_orders=False))
        self.assertEqual(legends.polygons([], [[-8,-8,-2],[8,8,9]],64),[])

    def test_compact_mesh_preserves_face_colors_and_center(self):
        faces=[[(0,0,0),(4,0,0),(4,4,0),(0,4,0)],[(1,1,1),(2,1,1),(2,2,1),(1,2,1)]]
        data=scene.encode('key-test',faces,144,16,face_colors=[144,96],precomputed_orders=False)
        decoded=scene.decode(data)
        self.assertEqual([f['color'] for f in decoded['faces']],[144,96])
        self.assertEqual(len(decoded['vertices']),9)
        self.assertNotIn(b'ORDE',dict(scene.blocks(data)))
        anchored=scene.decode(scene.encode('drive',faces,64,16,
                                           precomputed_orders=False,sort_center=(0,0,100)))
        self.assertEqual(anchored['vertices'][-1],(0,0,100))
        self.assertEqual(anchored['bounds'],decoded['bounds'])
        for colors in [[144],[144,250]]:
            with self.assertRaises(ValueError):
                scene.encode('key-test',faces,144,16,face_colors=colors)
