import json
from pathlib import Path
import struct
import tempfile
import unittest
from PIL import Image
import prepare
import presentation
from credit_story import diagram
from music import write_credit_schedule


class StoryTests(unittest.TestCase):
    def test_shared_palette_and_exact_reveal_payload(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);paths=[]
            for i,color in enumerate(['red','green','blue']):
                path=root/f'{i}.png';Image.new('RGB',(160,100),color).save(path);paths.append(path)
            target=root/'CARD.CRD'
            prepare.make_card(paths[-1],['Test'],target,root/'preview.png',paths,80)
            data=target.read_bytes()
            self.assertEqual(data[:4],b'CRD2')
            self.assertEqual(struct.unpack_from('<HH',data,80772),(3,80))
            self.assertEqual(len(data),80776+3*16000)
            palette=[tuple(data[4+i:4+i+3]) for i in range(0,768,3)]
            for i,color in enumerate([(63,0,0),(0,32,0),(0,0,63)]):
                self.assertEqual(palette[data[80776+i*16000]],color)
            self.assertEqual(data[64772:80772],data[-16000:])

    def test_story_order_and_reading_time(self):
        config,_,files=presentation.load();cards=json.loads(files['credits'].read_text())
        ids=[c['image'] for c in cards]
        self.assertEqual(len(set(ids)),21)
        self.assertLess(ids.index('main-ram'),ids.index('drives'))
        self.assertLess(ids.index('diskette'),ids.index('keyboard'))
        self.assertLess(ids.index('keyboard-interface'),ids.index('crt-controller'))
        self.assertLess(ids.index('monitor'),ids.index('psu'))
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            write_credit_schedule(Path(__file__).parent.parent/'MAIN/MUSIC0.S3M',root,config['transition'],21)
            cues=json.loads((root/'credit-cues.json').read_text())
            for card,cue in zip(cards,cues):
                view=card.get('view',{})
                motion=96 if view.get('cutaway') or view.get('diagram') in ('clock','matrix','video') else 80 if view.get('reveal') else 0
                self.assertGreaterEqual(cue['exit_start_cs']-cue['enter_end_cs']-motion,250)
            self.assertEqual(cues[-1]['end_cs'],10412)

    def test_diagrams_are_distinct_final_resolution_images(self):
        images=[diagram(kind,None) for kind in ['clock','matrix','video']]
        self.assertEqual(len({im.tobytes() for im in images}),3)
        for im in images:
            self.assertEqual(im.size,(160,100));self.assertEqual(im.mode,'RGB')


class AuthoringTests(unittest.TestCase):
    def test_preview_uses_quantized_frames_and_keeps_reading_interval(self):
        from preview_credit import decode,export_preview
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);frames=[]
            for n,color in enumerate(['red','blue']):
                p=root/f'{n}.png';Image.new('RGB',(160,100),color).save(p);frames.append(p)
            path=root/'CARD.CRD';prepare.make_card(frames[-1],['Example'],path,root/'draft.png',frames,96)
            cue={'order':28,'row':0,'start_cs':0,'enter_end_cs':84,'exit_start_cs':432,'end_cs':468}
            report=export_preview(path,cue,root/'preview')
            self.assertEqual(report['static_reading_seconds'],2.52)
            with Image.open(root/'preview/reveal.png') as im:
                self.assertEqual(im.n_frames,2)
                self.assertEqual(im.info['duration'],960)
                im.seek(1);self.assertEqual(im.info['duration'],2520)
            path.write_bytes(path.read_bytes()[:-1])
            with self.assertRaises(ValueError):decode(path)

    def test_claim_index_rejects_stale_text_and_missing_evidence(self):
        import claim_index
        original=json.loads(claim_index.DEFAULT.read_text())
        claim_index.validate()
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'claims.json'
            altered=json.loads(json.dumps(original));altered['claims'][1]['text']='Unreviewed assertion'
            p.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError,'Credit text changed'):claim_index.validate(p)
            altered=json.loads(json.dumps(original));altered['claims'][1]['sources']=[]
            p.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError,'Missing claim evidence'):claim_index.validate(p)

    def test_key_data_has_one_shot_motion_and_static_endpoint(self):
        from credit_story import diagram
        photo=Image.new('RGB',(70,48),'#303333')
        images=[diagram('matrix',photo,n/15) for n in range(16)]
        self.assertEqual(len({im.tobytes() for im in images}),16)
        self.assertEqual(images[-1].tobytes(),diagram('matrix',photo).tobytes())

if __name__=='__main__':unittest.main()
