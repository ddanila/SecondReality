import json
from pathlib import Path
import struct
import tempfile
import unittest

from expansion import INTRO, POST, launcher, write_schedule
from expansion_checks import verify


class ExpansionTests(unittest.TestCase):
    def test_intro_schedule_matches_real_phrase_boundaries(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'FX.TIM'
            scenes=write_schedule(path,INTRO)
            self.assertEqual([s['milliseconds'] for s in scenes],[7385,22153,7385])
            data=path.read_bytes()
            magic,first,last,count,rows=struct.unpack_from('<4s4I',data)
            self.assertEqual((magic,first,last,count,rows),(b'FX01',42,50,3,576))
            self.assertEqual(len(data),20+rows*4+count*20)

    def test_launcher_preserves_short_and_selects_modules_explicitly(self):
        from build import masm_source
        short=masm_source(True,True)
        self.assertNotIn("exefx db",short)
        expanded=launcher('expanded')
        self.assertIn('push    42 ; expansion MUSIC1 entry',expanded)
        self.assertIn('mov dx,si',expanded)
        self.assertIn('mov bx,18\n        mov cx,45000\n        call restartmus',expanded)
        self.assertIn('call rt_exec32',expanded)
        self.assertIn('mov bx,28\n',launcher('extended'))
        self.assertIn('mov ax,28\n        call rt_exp_wait',launcher('extended'))
        self.assertIn('jmp local_global_rt_sequence_done',launcher('scene'))

    def test_expansion_trace_rejects_skipped_or_late_scenes(self):
        with tempfile.TemporaryDirectory() as folder:
            scenes=write_schedule(Path(folder)/'FX.TIM',INTRO)
        log=('ENTRY scene=IDENTITY order=42 row=1 frames=0\n'
             'ENTRY scene=LENS order=43 row=0 frames=200\n'
             'ENTRY scene=TUNNEL order=47 row=0 frames=600\n'
             'END order=50 row=0 frames=1000\nCOMPLETE\n')
        self.assertEqual(verify(log,scenes)['end'],[50,0])
        for bad in [log.replace('scene=LENS','scene=GLENZ'),log.replace('row=0 frames=600','row=8 frames=600'),log.replace('COMPLETE\n','')]:
            with self.assertRaises(ValueError):verify(bad,scenes)

    def test_schedule_rejects_gaps_and_unreachable_rows(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'FX.TIM'
            for scenes in [[], [('lens',42,0,42,0)], [('lens',42,0,43,0),('tunnel',44,0,45,0)], [('lens',46,0,47,0)]]:
                with self.assertRaises(ValueError):write_schedule(path,scenes)

    def test_native_effects_are_live_deterministic_and_clipped(self):
        import shutil
        import subprocess
        if not shutil.which('cc'):self.skipTest('Native C compiler not installed')
        here=Path(__file__).resolve().parent
        with tempfile.TemporaryDirectory() as folder:
            folder=Path(folder);exe=folder/'effect'
            subprocess.run(['cc','-O1','-DFX_HOST',str(here/'effects.c'),'-o',str(exe),'-lm'],check=True)
            (folder/'FX.MSH').write_bytes(struct.pack('<I6f',2,0,-470,340,0,-125,324)+struct.pack('<9h2B',-640,0,2000,640,0,2000,0,0,3120,220,1)+struct.pack('<9h2B',-640,0,2000,640,0,2000,0,0,3120,220,0)+bytes(640*288))
            (folder/'FX.IMG').write_bytes(bytes((x//3+y//2)%128 for y in range(400) for x in range(640))*6)
            (folder/'FX.CRT').write_bytes(struct.pack('<2f',320,160)+bytes([70])*256000+bytes(int(160<x<480 and 70<y<280) for y in range(400) for x in range(640)))
            (folder/'FX.FNT').write_bytes(bytes(95*96))
            (folder/'FX.LOC').write_bytes(struct.pack('<6f',320,200,340,210,300,190))
            pts=[(x,y) for x in range(80,240,8) for y in range(60,140,8)]
            (folder/'FX.PTS').write_bytes(struct.pack('<I',len(pts))+b''.join(struct.pack('<hh',*p) for p in pts))
            (folder/'FX.GEO').write_bytes(struct.pack('<I',4)+b''.join(struct.pack('<I6f',i,-100,-80,i*10,100,80,i*10+20) for i in range(4)))
            for scene in range(12):
                command=[str(exe),str(scene),'3','14.769','-']
                first=subprocess.check_output(command,cwd=folder)
                again=subprocess.check_output(command,cwd=folder)
                self.assertTrue(first==again, f"Nondeterministic scene {scene}")
                self.assertEqual(len(first),15+320*200*3)
                self.assertTrue(any(first[15:]))
                command[2]='6'
                self.assertTrue(first!=subprocess.check_output(command,cwd=folder), f"Static scene {scene}")
            # The DOS path reads a compact mesh and 16-bit visible IDs. Compare
            # selective lists against full geometry at identical normalized poses.
            import os
            (folder/'FX.DRW').write_bytes((folder/'FX.MSH').read_bytes())
            cache=struct.pack('<4sI',b'FV02',3)
            for scene,index in [(3,0),(10,1),(11,1)]:
                cache+=struct.pack('<II',scene,3)+struct.pack('<IH',1,index)*3
            (folder/'FX.VIS').write_bytes(cache)
            for scene in (3,10,11):
                command=[str(exe),str(scene),'7.3845','14.769','-']
                cached=subprocess.check_output(command,cwd=folder)
                full=subprocess.check_output(command,cwd=folder,env=dict(os.environ,FX_VIS_BAKE='1'))
                self.assertEqual(cached,full)
            (folder/'FX.VIS').write_bytes(struct.pack('<4sIIIIH',b'FV02',1,3,2,1,2))
            bad=subprocess.run([str(exe),'3','3','14.769','-'],cwd=folder,capture_output=True)
            self.assertNotEqual(bad.returncode,0)
            self.assertIn(b'visibility id',bad.stderr)

