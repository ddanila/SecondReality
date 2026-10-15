"""Cache loader rejects stale/corrupt input before any drawing or face culling."""
import ctypes,os,shutil,struct,subprocess,tempfile,unittest
from pathlib import Path
import bake,route_cache

@unittest.skipUnless(shutil.which('cc'),'Host compiler required')
class BakedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
        (cls.path/'dos.h').write_text('#include <sys/stat.h>\nstatic int _dos_getfileattr(const char *n,unsigned *a){struct stat s;*a=0;return stat(n,&s);}\n')
        (cls.path/'bake_signature.h').write_text('#define RT_BAKE_SIGNATURE 1715UL\n')
        (cls.path/'loader.c').write_text('''#include "baked.c"
int rt_ram_color=1;
unsigned draws,mask_draws;
int rt_detail_enabled(void){return 1;}
void rt_raster(rt_vertex *v,int n,int decal){draws++;}
void rt_detail_masks(const unsigned char *p,unsigned n){mask_draws+=n;}
''')
        subprocess.run(['cc','-O2','-shared','-fPIC','-DRT_HOST_TEST','-D__cdecl=','-I'+str(cls.path),'-I'+str(bake.HERE),str(cls.path/'loader.c'),'-o',str(cls.path/'loader.so')],check=True)
        cls.lib=ctypes.CDLL(str(cls.path/'loader.so'));cls.lib.rt_baked_init.argtypes=[ctypes.c_ulong,ctypes.c_uint]
        cls.compress=staticmethod(bake.compressor())
    @classmethod
    def tearDownClass(cls):cls.lib.rt_baked_close();cls.tmp.cleanup()
    def setUp(self):
        self.cwd=Path.cwd();os.chdir(self.path);self.lib.rt_baked_close()
        (self.path/'U2E.BKC').unlink(missing_ok=True)
        ctypes.c_uint.in_dll(self.lib,'draws').value=0;ctypes.c_uint.in_dll(self.lib,'mask_draws').value=0
    def tearDown(self):self.lib.rt_baked_close();os.chdir(self.cwd)
    def payload(self,masks=None):
        masks=masks or [struct.pack('<HHHBB',3210,1,2000,63,255)]
        command=b'\x03\x00'+b''.join(struct.pack('<hhHB',x,y,2000,80) for x,y in [(10,10),(20,10),(20,20)])
        return struct.pack('<IIII',1,1,len(masks),65537)+command+b''.join(masks)
    def write(self,payload=None,signature=1715,hash=123,block=None,checksum=None):
        payload=payload or self.payload();block=self.compress(payload) if block is None else block
        checksum=route_cache.fnv(payload) if checksum is None else checksum
        raw=struct.pack('<4sIIIII',b'BKC1',signature,hash,1,2,len(payload))+struct.pack('<IIII',0,len(block),len(payload),checksum)+block
        (self.path/'U2E.BKC').write_bytes(raw)
    def test_valid_cache_draws_and_selects_faces(self):
        self.write();self.lib.rt_baked_init(123,2)
        self.assertEqual(self.lib.rt_baked_prepare(0),1)
        self.assertTrue(self.lib.rt_baked_face(1,0));self.assertFalse(self.lib.rt_baked_face(1,1))
        self.lib.rt_baked_draw();self.lib.rt_baked_finish()
        self.assertEqual(ctypes.c_uint.in_dll(self.lib,'draws').value,1)
        self.assertEqual(ctypes.c_uint.in_dll(self.lib,'mask_draws').value,1)
        self.assertEqual(self.lib.rt_baked_prepare(1),0)
        self.assertTrue(self.lib.rt_baked_face(1,1))
    def test_missing_stale_and_corrupt_cache_fall_back(self):
        self.lib.rt_baked_init(123,2);self.assertEqual(self.lib.rt_baked_prepare(0),0)
        for kwargs in [{'signature':0},{'hash':124},{'checksum':0},{'block':b'\xf0'}]:
            self.lib.rt_baked_close();self.write(**kwargs);self.lib.rt_baked_init(123,2)
            self.assertEqual(self.lib.rt_baked_prepare(0),0,kwargs)
            self.assertTrue(self.lib.rt_baked_face(1,1))
            self.assertEqual(ctypes.c_uint.in_dll(self.lib,'draws').value,0)
    def test_invalid_mask_layout_is_rejected_even_with_valid_checksum(self):
        a=struct.pack('<HHHBB',3210,1,2000,63,255)
        for masks in [[a,a],[struct.pack('<HHHBB',64000,1,2000,63,255)],[a,struct.pack('<HHHBB',3000,2,2000,63,255)]]:
            self.lib.rt_baked_close();self.write(self.payload(masks));self.lib.rt_baked_init(123,2)
            self.assertEqual(self.lib.rt_baked_prepare(0),0)
