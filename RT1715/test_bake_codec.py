"""Bounded DOS cache decoding: valid literals, overlap and malformed blocks."""
import ctypes,random,shutil,subprocess,tempfile,unittest
from pathlib import Path
import bake

@unittest.skipUnless(shutil.which('cc'),'Host compiler required')
class CodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();p=Path(cls.tmp.name)
        (p/'codec.c').write_text('#include "bake_codec.h"\n')
        subprocess.run(['cc','-O2','-shared','-fPIC','-I'+str(bake.HERE),str(p/'codec.c'),'-o',str(p/'codec.so')],check=True)
        cls.lib=ctypes.CDLL(str(p/'codec.so'));cls.lib.rt_unpack_block.argtypes=[ctypes.c_char_p,ctypes.c_uint,ctypes.c_void_p,ctypes.c_uint]
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def decode(self,block,n):
        out=ctypes.create_string_buffer(b'guard'+bytes(n)+b'guard',n+10)
        result=self.lib.rt_unpack_block(block,len(block),ctypes.byref(out,5),n)
        self.assertEqual(out.raw[:5],b'guard');self.assertEqual(out.raw[-5:],b'guard')
        return result,out.raw[5:-5]
    def test_literals_and_overlapping_match(self):
        self.assertEqual(self.decode(b'\x30abc',3),(1,b'abc'))
        self.assertEqual(self.decode(b'\x15a\x01\x00\x00',10),(1,b'a'*10))
    def test_bad_lengths_offsets_and_truncation(self):
        for block,n in [(b'\xf0',20),(b'\x30ab',3),(b'\x30abc',2),(b'\x00\x00\x00',4),(b'\x00\x01\x00',4),(b'\x1fa\x01\x00\xff',100)]:
            self.assertEqual(self.decode(block,n)[0],0)
    def test_host_compressor_round_trip(self):
        compress=bake.compressor();rng=random.Random(1715)
        for n in [12,20,255,256,4096,65536,262144]:
            for raw in [bytes(rng.randrange(256) for _ in range(n)),(b'pose mask depth '*n)[:n],bytes(n)]:
                self.assertEqual(self.decode(compress(raw),n),(1,raw))
