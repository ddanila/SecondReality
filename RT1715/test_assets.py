"""Format and safety checks; run with python3 -m unittest discover -s RT1715."""
import json
import shutil
from pathlib import Path
import struct
import tempfile
import unittest

from PIL import Image
import prepare
import scene


class SceneTests(unittest.TestCase):
    def test_all_original_meshes_decode(self):
        objects = scene.inventory(prepare.ORIGINAL)
        self.assertEqual(len(objects),42)
        self.assertEqual(objects[27]["name"], '"s01"')
        self.assertEqual([o["slot"] for o in objects if o["protected"]],[28])

    def test_generated_mesh_layout_normal_and_orders(self):
        triangles = [[(0,0,0),(100,0,0),(0,100,0)],[(0,0,0),(0,0,100),(100,0,0)]]
        binary = scene.encode('"test"',triangles)
        mesh = scene.decode(binary)
        self.assertEqual(mesh["bounds"],[[0,100],[0,100],[0,100]])
        chunks = scene.blocks(binary)
        self.assertEqual(sum(tag==b"ORDE" for tag,_ in chunks),8)
        normals = dict(chunks)[b"NORM"]
        self.assertEqual(struct.unpack_from("<hhh",normals,4),(0,0,16384))
        for tag, data in chunks:
            if tag.startswith(b"ORD"):
                words, probe, a, b, end = struct.unpack_from("<5H",data)
                self.assertEqual((words,end),(5,0))
                self.assertEqual({a,b},{2,14})
                self.assertLess(probe,len(mesh["vertices"]))

    def test_uniform_fit_keeps_aspect_and_ground(self):
        faces = [[(0,0,0),(2,0,0),(0,1,4)]]
        fitted = scene.fit_mesh(faces,[[10,20],[30,40],[50,70]])
        self.assertEqual(fitted, [[(10,32,50),(20,32,50),(10,38,70)]])

    def test_bad_geometry_rejected(self):
        for triangles in [[], [[(0,0,0)]*3]]:
            with self.assertRaises(ValueError): scene.encode("bad",triangles)
        with self.assertRaises(ValueError):
            scene.encode("bad",[[(0,0,0),(1,0,0),(0,1,0)]],240,32)
        with self.assertRaises(ValueError): scene.blocks(b"VERT"+struct.pack("<I",8)+b"\0")

    def test_binary_stl_not_guessed_from_header(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"test.stl"
            path.write_bytes(b"solid"+bytes(75)+struct.pack("<I",1)+
                             struct.pack("<12fH",0,0,1,0,0,0,1,0,0,0,1,0,0))
            self.assertEqual(scene.read_stl(path),[[(0,0,0),(1,0,0),(0,1,0)]])
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaises(ValueError): scene.read_stl(path)


class CreditTests(unittest.TestCase):
    def test_all_printable_ascii_and_invalid_text(self):
        prepare.printable(["".join(chr(i) for i in range(32,80)),
                           "".join(chr(i) for i in range(80,127))])
        for lines in [[], ["line\nbreak"], ["tab\t"], ["caf\u00e9"], ["\x7f"], ["x"*51], ["a"]*5]:
            with self.assertRaises(ValueError): prepare.printable(lines)

    def test_card_palette_and_buffers(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            Image.new("RGB",(200,150),(100,150,200)).save(base/"source.png")
            prepare.make_card(base/"source.png",["ASCII abc XYZ 123 !@#"],base/"card.crd",base/"preview.png")
            data = (base/"card.crd").read_bytes()
            self.assertEqual(len(data),4+768+64000+16000)
            self.assertEqual(data[:4],b"CRD1")
            self.assertLessEqual(max(data[4:772]),63)
            self.assertLessEqual(max(data[772:64772]),15)
            self.assertGreaterEqual(min(data[64772:]),16)
            self.assertTrue(any(data[772:64772]))
            with Image.open(base/"preview.png") as preview:
                self.assertEqual(preview.size,(640,480))

    def test_protected_slot_and_typo_fail_before_conversion(self):
        config = json.loads((prepare.HERE/"assets/example.json").read_text())
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/"project.json"
            config["models"][0]["slot"] = 28
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError,"protected drone"):
                prepare.load_project(path)
            config["models"][0]["slot"] = 2
            config["models"][0]["colour"] = 32
            path.write_text(json.dumps(config))
            with self.assertRaisesRegex(ValueError,"Unknown model"):
                prepare.load_project(path)

    def test_existing_image_workflow_needs_no_openscad(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            build, dos = base/"build", base/"dos"
            build.mkdir()
            dos.mkdir()
            for name in ("U2E.028","U2E.00M","U2E.0AA","U2E.0AB"):
                shutil.copyfile(prepare.ORIGINAL/name,dos/name)
            Image.new("RGB",(160,100),(90,80,70)).save(base/"photo.png")
            (base/"project.json").write_text(json.dumps({"version":1,"credits":[
                {"image":"photo.png","lines":["Existing rendered photo"],"hold_frames":70}]}))
            report = prepare.prepare(base/"project.json",build,dos,"deliberately-missing-openscad")
            self.assertEqual((dos/"CRED.IDX").read_text(),"RT1715 1\nCARD01.CRD 70\n")
            self.assertEqual(len(report["protected"]),4)
            self.assertEqual(len((dos/"CARD01.CRD").read_bytes()),80772)


if __name__ == "__main__":
    unittest.main()
