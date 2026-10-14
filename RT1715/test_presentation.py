import json
from pathlib import Path
import struct
import tempfile
import unittest
import numpy as np
import presentation
import robotron
import scene
from music import write_credit_schedule


class PresentationTests(unittest.TestCase):
    def test_manifest_rejects_unreadable_text_missing_parts_and_files(self):
        original,source,files=presentation.load()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);config=dict(original)
            config['source']=str(source)
            for key,file in files.items():
                target=root/file.name;target.write_bytes(file.read_bytes());config[key]=target.name
            manifest=root/'presentation.json';manifest.write_text(json.dumps(config))
            presentation.load(manifest)
            cards=json.loads(files['credits'].read_text());cards[0]['lines']=['W'*50]
            (root/config['credits']).write_text(json.dumps(cards))
            with self.assertRaisesRegex(ValueError,'too small'):presentation.load(manifest)
            cards=json.loads(files['credits'].read_text());cards[0]['view']['parts']=['missing-board']
            (root/config['credits']).write_text(json.dumps(cards))
            with self.assertRaisesRegex(ValueError,'Missing model parts'):presentation.load(manifest)
            cards=json.loads(files['credits'].read_text());cards[0].pop('view');cards[0]['photo']='absent.png'
            (root/config['credits']).write_text(json.dumps(cards))
            with self.assertRaisesRegex(ValueError,'Missing photo'):presentation.load(manifest)

    def test_quintic_drone_has_continuous_acceleration_and_restrained_bank(self):
        flight=json.loads((robotron.HERE/'assets/robotron/flight.json').read_text());keys=flight['drone']
        def acceleration(t):
            h=.0001
            return (robotron.sample_track(keys,t+h,'position')-2*robotron.sample_track(keys,t,'position')+robotron.sample_track(keys,t-h,'position'))/(h*h)
        for key in keys[1:-1]:
            t=key['time']
            left=2*acceleration(t-.0002)-acceleration(t-.0004)
            right=2*acceleration(t+.0002)-acceleration(t+.0004)
            np.testing.assert_allclose(left,right,atol=.2)
        banks=[]
        for t in np.linspace(0,48.1,300):
            r=robotron.drone_rotation(flight,t);left=np.cross([0,0,1.],r[:,0]);left/=np.linalg.norm(left)
            bank=np.arccos(np.clip(np.dot(left,r[:,1]),-1,1));banks.append(bank)
        self.assertLessEqual(max(banks),np.radians(16)+1e-9)

    def test_screen_smooth_normals_are_valid_and_do_not_change_geometry(self):
        from robotron_lod import crt_surround
        faces=robotron.polygons(crt_surround()[0])
        original=scene.encode('screen',faces,64,16,precomputed_orders=False)
        smooth=scene.encode('screen',faces,64,16,precomputed_orders=False,smooth=True)
        a,b=scene.decode(original),scene.decode(smooth)
        self.assertEqual(a['bounds'],b['bounds']);self.assertEqual(a['vertices'],b['vertices'])
        self.assertTrue(all(face['flags']&0x1000 for face in b['faces']))
        chunks=dict(scene.blocks(smooth))
        count=struct.unpack_from('<H',chunks[b'NORM'])[0]
        self.assertLessEqual(count,500)
        used={i for face in b['faces'] for i in face['indices']}
        for i in used:
            normal=struct.unpack_from('<h',chunks[b'VERT'],4+i*16+12)[0]
            self.assertTrue(0<=normal<count)

    def test_cards_enter_on_beats_and_keep_the_original_end(self):
        config,_,_=presentation.load()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);write_credit_schedule(robotron.HERE.parent/'MAIN/MUSIC0.S3M',root,config['transition'],21)
            cues=json.loads((root/'credit-cues.json').read_text())
            self.assertEqual((cues[0]['order'],cues[0]['row']),(28,0))
            self.assertEqual(cues[-1]['end_cs'],10412)
            self.assertEqual((root/'CRED.TIM').stat().st_size,2048)
            for cue in cues:
                self.assertEqual(cue['row']%8,0)
                self.assertGreaterEqual(cue['exit_start_cs']-cue['enter_end_cs'],300)
            for a,b in zip(cues,cues[1:]):self.assertLess(a['end_cs'],b['start_cs'])

    def test_playback_checks_every_card_entry_and_end(self):
        from run import verify_card_schedule
        config,_,_=presentation.load()
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);write_credit_schedule(robotron.HERE.parent/'MAIN/MUSIC0.S3M',root,config['transition'],21)
            cues=json.loads((root/'credit-cues.json').read_text())
            log=''.join(f"ENTRY order={c['order']} row={c['row']}\n" for c in cues)+'END order=43 row=29\n'
            report=verify_card_schedule(log,(root/'CRED.CUE').read_text(),(root/'CRED.TIM').read_bytes())
            self.assertEqual(report['entry_error_cs'],[0]*21)
            with self.assertRaises(ValueError):verify_card_schedule(log.replace('ENTRY order=28 row=0','ENTRY order=28 row=8'),(root/'CRED.CUE').read_text(),(root/'CRED.TIM').read_bytes())
            with self.assertRaises(ValueError):verify_card_schedule(log.replace('END order=43 row=29','END order=43 row=35'),(root/'CRED.CUE').read_text(),(root/'CRED.TIM').read_bytes())
