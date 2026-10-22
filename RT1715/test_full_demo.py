"""Full-demo asset and synchronization contracts (host-only)."""
import struct,tempfile,unittest,math
from pathlib import Path
import numpy as np
from PIL import Image
from full_art import packed_picture
from full_compare import align
from full_demo import read_trace,launcher


class FullDemoTests(unittest.TestCase):
    def test_opening_font_spacing_and_punctuation(self):
        from full_opening import released_font, encode, EXTRA
        from full_build import unpack
        _, glyphs = released_font(unpack('ALKU.EXE'))
        self.assertFalse(glyphs[' '].any())
        self.assertGreater(np.count_nonzero(np.any(glyphs['/'], axis=1)), 10)
        self.assertNotEqual(encode('/'), b"'")
        for accented, base in zip('äöü', 'aou'):
            np.testing.assert_array_equal(glyphs[accented][4:], glyphs[base][4:])
            self.assertFalse(glyphs[accented][2:4].any())
            self.assertTrue(glyphs[accented][:2].any())
        self.assertEqual(encode('ö')[0], 128 + EXTRA.index('ö'))

    def test_space_diskette_preserves_attitude_and_openings(self):
        import full_space, scene
        with tempfile.TemporaryDirectory() as tmp:
            output=full_space.build(tmp)
            mesh=scene.decode((output/'U2A.002').read_bytes())
            spans=np.diff(np.array(mesh['bounds']),axis=1).ravel()
            self.assertLess(spans[2], min(spans[:2])*.30)
            self.assertLessEqual(len(mesh['faces']),scene.MAX_FACES)
            self.assertTrue({2,8,16,28}.issubset({f['color'] for f in mesh['faces']}))
            # Hub center must remain an actual opening through all layers.
            import trimesh
            m=trimesh.Trimesh(vertices=mesh['vertices'],faces=[f['indices'] for f in mesh['faces']],process=False)
            center=np.mean(np.array(mesh['bounds']),axis=1)
            from keycaps import hits
            direction=np.array([0.,-math.sin(math.radians(15)),math.cos(math.radians(15))])
            locations=hits(m,center+direction*10000,-direction)
            self.assertEqual(len(locations),0)

    def test_water_relocation_preserves_code_stack_and_mask(self):
        from full_water import water_projection
        from full_build import unpack
        from build import HERE
        old=unpack('MNTSCRL.EXE').read_bytes()
        draft=Image.open(HERE/'assets/full-demo/art/water-draft.png').convert('RGB').resize((320,200))
        with tempfile.TemporaryDirectory() as tmp:
            new=water_projection(old,draft,Path(tmp))
            h=struct.unpack_from('<14H',old);nh=struct.unpack_from('<14H',new)
            self.assertEqual(nh[7:9],h[7:9]) # unchanged SS:SP
            self.assertEqual((nh[2]-1)*512+(nh[1] or 512),len(new))
            base=h[4]*16;allowed=set(range(2,6))|{18,19};relocated=[]
            for i in range(h[3]):
                off,seg=struct.unpack_from('<HH',old,h[12]+4*i);at=base+seg*16+off
                if old[at:at+2]!=new[at:at+2]:
                    allowed.update((at,at+1));relocated.append(base+16*struct.unpack_from('<H',new,at)[0])
            self.assertEqual(len(relocated),3)
            mask=np.asarray(Image.open(Path(tmp)/'water-projection-mask.png')).ravel()
            addresses=[]
            for at in relocated:
                self.assertGreaterEqual(at,len(old)+h[5]*16)
                for _ in range(237*31):
                    count=struct.unpack_from('<H',new,at)[0];at+=2
                    addresses.extend(struct.unpack_from(f'<{count}H',new,at));at+=2*count
            self.assertEqual(len(addresses),len(set(addresses)))
            self.assertEqual(set(addresses),set(np.flatnonzero(mask)))
            self.assertTrue(all(a==b or i in allowed for i,(a,b) in enumerate(zip(old,new))))

    def test_water_shadow_dims_water_and_letters(self):
        from full_water import water,tape_masks
        from full_build import unpack
        from build import HERE,ROOT
        released=unpack('MNTSCRL.EXE')
        original=(ROOT/'FOREST/HILLBACK.CLX').read_bytes()
        offset=released.read_bytes().index(original)
        draft=Image.open(HERE/'assets/full-demo/art/water-draft.png').convert('RGB').resize((320,200),Image.Resampling.LANCZOS)
        tape,shadow=tape_masks(draft)
        self.assertGreater(np.count_nonzero(shadow),1000)
        self.assertFalse(np.any(tape&shadow))
        with tempfile.TemporaryDirectory() as tmp:
            exe=water(released,Path(tmp))[0].read_bytes()
            palette=np.frombuffer(exe[offset+10:offset+778],dtype=np.uint8).reshape(256,3)
            pixels=np.frombuffer(exe[offset+778:offset+778+64000],dtype=np.uint8).reshape(200,320)
            self.assertTrue(np.all((pixels[shadow]>=16)&(pixels[shadow]<=30)))
            self.assertTrue(np.all(pixels[~tape]<=30))
            self.assertTrue(np.all(pixels[tape]>=32))
            for i in range(1,16):
                self.assertTrue(np.all(palette[i+15]<=palette[i]))
            lookup=np.frombuffer((Path(tmp)/'water-blend.bin').read_bytes(),dtype=np.uint8).reshape(32,8)
            colors=palette[lookup[1:31,1:]]
            # Surface brightness must vary across a single lettering shade.
            self.assertGreater(np.ptp(colors[:15,-1].astype(float).mean(axis=1)),8)
            self.assertTrue(np.all(colors[15:].mean(axis=(1,2))<colors[:15].mean(axis=(1,2))))
            self.assertTrue(np.all((lookup[1:31,1:]>=129)&(lookup[1:31,1:]<=159)))
            self.assertGreaterEqual(len(np.unique(colors[:15].reshape(-1,3),axis=0)),14)

    def test_shaded_water_projector_relocation(self):
        from full_water import shaded_projector
        from full_build import unpack
        old=unpack('MNTSCRL.EXE').read_bytes()
        # Production appends after the UV tables and reserved BSS/stack.
        h=struct.unpack_from('<14H',old);base=h[4]*16
        padded=old+bytes(h[5]*16)
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp)/'water-blend.bin').write_bytes(bytes(256))
            new=shaded_projector(padded,Path(tmp))
            nh=struct.unpack_from('<14H',new)
            self.assertEqual(nh[3],h[3]+1)
            self.assertEqual(nh[7:9],h[7:9])
            self.assertEqual((nh[2]-1)*512+(nh[1] or 512),len(new))
            off,seg=struct.unpack_from('<HH',new,h[12]+4*h[3])
            entry=base+seg*16+off-3
            self.assertEqual(new[entry],0xea)
            target=base+16*struct.unpack_from('<H',new,entry+3)[0]
            self.assertGreaterEqual(target,len(padded))
            self.assertEqual(new[target:],(Path(tmp)/'water-projector.bin').read_bytes())
            self.assertEqual(old[base:entry],new[base:entry])
            self.assertEqual(old[entry+5:],new[entry+5:len(old)])

    def test_key_wall_preserves_rest_of_flight(self):
        import animation,full_flyover,shutil
        from build import HERE
        with tempfile.TemporaryDirectory() as tmp:
            dos=Path(tmp)/'dos';dos.mkdir()
            shutil.copyfile(HERE/'build/dos/U2E.00M',dos/'U2E.00M')
            full_flyover.build(dos,bake_cache=False)
            count=len(animation.mapping((dos/'U2E.00M').read_bytes()))
            original=animation.decode((HERE/'build/dos/U2E.0AB').read_bytes(),count)
            updated=animation.decode((dos/'U2E.0AB').read_bytes(),count)
            self.assertEqual(len(original),len(updated))
            self.assertLess(updated[0][1],original[0][1])
            a=[[0]*12 for _ in range(count)];b=[[0]*12 for _ in range(count)]
            va=[False]*count;vb=[False]*count
            for i,((ra,fa),(rb,fb)) in enumerate(zip(original,updated)):
                for r in ra:a[r['object']]=r['state'];va[r['object']]=r['visible']
                for r in rb:b[r['object']]=r['state'];vb[r['object']]=r['visible']
                if i>=175:
                    self.assertEqual(a,b);self.assertEqual(va,vb);self.assertEqual(fa,fb)

    def test_full_builder_preserves_reviewed_cut(self):
        from full_demo import build
        from build import HERE
        for target in (HERE/'build',HERE/'build/dos/nested'):
            with self.assertRaisesRegex(ValueError,'reviewed short'):
                build(target)

    def test_plasma_clipping_bounds(self):
        # Exercise the C scan converter independently of DOS, with 32-bit
        # arithmetic and a span-writer stub that checks its assembly contract.
        import subprocess,re
        source=(Path(__file__).parent/'full-scenes/plasma-fill.c').read_text()
        source=re.sub(r'\blong\b','int32_t',source)
        source=re.sub(r'(\d)L\b',r'\1',source)
        harness=r"""
#include <stdint.h>
#include <assert.h>
#include <stdlib.h>
#include <math.h>
#define MK_FP(a,b) ((char *)0)
char memory[134][160],(*vmem)[160]=memory,*to,*from;
int clrtau[8][256][2],clrptr,kuvataus[4],disttaus[4],dseg,yy,*ctau;
int32_t ax1,ax2,tax1,tax2,tay1,tay2,xx1,xx2,txx1,txx2,txy1,txy2;
int spans;
int do_block(int count) {
    assert(count==1&&yy>=0&&yy<134);
    assert(xx2>=0&&xx1>=xx2&&xx1<=639*65536);
    assert((xx1>>18)-(xx2>>18)<200);
    assert(txx1>=0&&txx1<=256*65536&&txx2>=0&&txx2<=256*65536);
    assert(txy1>=0&&txy1<=64*65536&&txy2>=0&&txy2<=64*65536);
    assert(ctau==&clrtau[0][yy][0]);spans++;return 0;
}
"""
        main=r"""
int main(void) {
    int i,j,x[4],y[4],cx,cy,w,h;double angle,xx,yy;
    for(i=0;i<2000;i++) {
        cx=rand()%1600-500;cy=rand()%600-250;
        w=1+rand()%600;h=1+rand()%300;angle=i*.37;
        for(j=0;j<4;j++) {
            xx=(j==0||j==3)?-w:w;yy=j<2?-h:h;
            x[j]=cx+xx*cos(angle)-yy*sin(angle);
            y[j]=cy+xx*sin(angle)+yy*cos(angle);
        }
        do_poly(x[0],y[0],x[1],y[1],x[2],y[2],x[3],y[3],0,0);
    }
    assert(spans>10000);return 0;
}
"""
        with tempfile.TemporaryDirectory() as tmp:
            c=Path(tmp)/'clip.c';exe=Path(tmp)/'clip';c.write_text(harness+source+main)
            subprocess.run(['cc','-std=gnu89','-Wno-implicit-int','-fsanitize=undefined,address',str(c),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

    def test_picture_round_trip_and_black_background(self):
        rng=np.random.default_rng(1715)
        pixels=rng.integers(0,256,(400,320,3),dtype=np.uint8);pixels[:10]=0
        encoded,quant=packed_picture(Image.fromarray(pixels),63)
        self.assertEqual(encoded[16:19],bytes(3));self.assertEqual(encoded[8:10],struct.pack('<H',49))
        rows=[];at=784
        for y in range(400):
            size=struct.unpack_from('<H',encoded,at)[0];at+=2;end=at+size;row=[]
            while at<end:
                value=encoded[at];at+=1
                if value&128:
                    row.extend([encoded[at]]*(value&127));at+=1
                else:row.append(value)
            self.assertEqual(len(row),320);rows.append(row)
        self.assertEqual(at,len(encoded));np.testing.assert_array_equal(rows,np.asarray(quant))
        self.assertGreater(len(encoded),65536)  # exercise segmented asset case

    def test_audio_alignment_and_drift_rejection(self):
        rng=np.random.default_rng(93);a=rng.normal(size=8000*24)
        b=np.concatenate((np.zeros(1000),a))
        offset,checks=align(a,b,0,20)
        self.assertAlmostEqual(offset,.125);self.assertGreater(min(c['correlation'] for c in checks),.99)
        drifting=np.concatenate((a[:88800],np.zeros(400),a[88800:]))
        with self.assertRaisesRegex(ValueError,'drift'):align(a,drifting,0,20)
        with self.assertRaises(ValueError):align(np.zeros_like(a),np.zeros_like(a),0,20)
        noisy=a.copy();noisy[4*8000:6*8000]=rng.normal(size=2*8000)
        offset,checks=align(a,noisy,0,20)
        self.assertAlmostEqual(offset,0)
        self.assertTrue(any(not c['reliable'] for c in checks))
        with self.assertRaisesRegex(ValueError,'match reliably'):
            align(a,rng.normal(size=a.shape),0,20)

    def test_scene_trace(self):
        row=b'ALKU.EXE\0'.ljust(16,b'\0')+struct.pack('<4HI',1,0,10,0,5613)+bytes(4)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'SCENES.BIN';p.write_bytes(row)
            self.assertEqual(read_trace(p)[0]['retrace'],5613)
            p.write_bytes(row[:-1])
            with self.assertRaises(ValueError):read_trace(p)

    def test_credit_edits_preserve_images_and_animation_bytes(self):
        from full_credits import build,EDITS
        from build import HERE
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'dos';p.mkdir()
            originals={}
            for number in EDITS:
                name=f'CARD{number:02}.CRD'
                originals[name]=(HERE/'build/dos'/name).read_bytes()
                (p/name).write_bytes(originals[name])
            for name in ('CRED.CUE','CRED.TIM'):(p/name).write_bytes((HERE/'build/dos'/name).read_bytes())
            before=(p/'CRED.CUE').read_text().splitlines()
            build(p)
            after=(p/'CRED.CUE').read_text().splitlines()
            self.assertEqual(before[:-1],after[:-1])
            self.assertEqual(int(after[-1].split()[-1]),10376)
            for name,old in originals.items():
                new=(p/name).read_bytes()
                self.assertEqual(len(new),len(old))
                self.assertEqual(new[:772],old[:772])
                self.assertEqual(new[64772:],old[64772:])
                self.assertLessEqual(max(new[772:64772]),15)

    def test_tape_round_holes_leader_and_message(self):
        from full_water import tape,tape_center
        from full_build import unpack
        from build import ROOT
        old=(ROOT/'WATER/MIEKKA.SCI').read_bytes()
        original=unpack('RAYSCRL.EXE');raw=original.read_bytes();at=raw.index(old)
        with tempfile.TemporaryDirectory() as d:
            exe=tape(original,Path(d))[0].read_bytes()
            delta=(struct.unpack_from('<H',exe,8)[0]-struct.unpack_from('<H',raw,8)[0])*16
            strip=np.frombuffer(exe[at+delta+778:at+delta+778+14000],dtype=np.uint8).reshape(35,400)
            message=b'THIS TAPE CANNOT PROVE WHAT IT SAYS'
            decoded=[]
            for i in range(len(message)):
                x=24+i*8;y=tape_center(x)
                decoded.append(sum(int(strip[y+dy,x]==0)<<bit for bit,dy in enumerate([-12,-9,-6,0,3,6,9,12])))
            self.assertEqual(bytes(decoded),message)
            for x in range(0,400,8):self.assertEqual(strip[tape_center(x)-3,x],0)
            for x in range(320,384,8):
                for dy in (-12,-9,-6,0,3,6,9,12):self.assertNotEqual(strip[tape_center(x)+dy,x],0)
            # T has bit 2 set. Cross-section is circular, not a filled square.
            x=24;y=tape_center(x)-6
            self.assertEqual(strip[y,x],0)
            self.assertEqual(strip[y,x+1],0)
            self.assertNotEqual(strip[y+1,x+1],0)
            h=struct.unpack_from('<14H',raw);nh=struct.unpack_from('<14H',exe);base=h[4]*16
            self.assertEqual(nh[3],h[3]+1)
            self.assertEqual(nh[7:9],h[7:9])
            off,seg=struct.unpack_from('<HH',exe,h[12]+4*h[3]);entry=base+delta+seg*16+off-3
            self.assertEqual(exe[entry],0x9a)
            target=base+delta+16*struct.unpack_from('<H',exe,entry+3)[0]
            self.assertGreaterEqual(target,len(raw)+h[5]*16)
            self.assertEqual(exe[base+delta:entry],raw[base:entry-delta])
            self.assertEqual(exe[entry+12:at+delta],raw[entry-delta+12:at])
            self.assertEqual(exe[at+delta+len(old):len(raw)+delta],raw[at+len(old):])

    def test_double_resolution_tape_texture_and_maps(self):
        from full_tape_hd import texture,maps,MESSAGE,TRACKS,build
        from full_water import tape_center
        from full_build import unpack
        image=texture()
        self.assertEqual(image.shape,(70,800))
        decoded=[]
        for i in range(len(MESSAGE)):
            x=24+i*8;y=tape_center(x)
            decoded.append(sum(int(image[2*(y+dy),2*x]==0)<<bit for bit,dy in enumerate(TRACKS)))
        self.assertEqual(bytes(decoded),MESSAGE)
        for x in range(0,400,8):self.assertEqual(image[2*(tape_center(x)-3),2*x],0)
        for old,new in maps():
            at=0;addresses=[]
            for i in range(158*34):
                count=struct.unpack_from('<H',old,at)[0];at+=2
                addresses.extend(struct.unpack_from(f'<{count}H',old,at));at+=count*2
            count=struct.unpack_from('<H',new)[0]
            records=np.frombuffer(new[2:],dtype='<u2').reshape(-1,3)
            self.assertEqual(count,len(addresses))
            self.assertEqual(set(records[:,0]),set(addresses))
            self.assertLess(len(new),65536)
            self.assertLessEqual(records[:,1].max(),315)
            self.assertLessEqual(records[:,2].max()+799,55999)
            self.assertGreater(np.count_nonzero((records[:,2]//800)%2),count//5)
        with tempfile.TemporaryDirectory() as tmp:
            raw=unpack('RAYSCRL.EXE').read_bytes();h=struct.unpack_from('<14H',raw)
            new=build(unpack('RAYSCRL.EXE'),tmp).read_bytes();nh=struct.unpack_from('<14H',new)
            self.assertEqual(nh[7:9],h[7:9])
            self.assertEqual(nh[3],h[3]+2)
            self.assertEqual((nh[2]-1)*512+(nh[1] or 512),len(new))
            base=nh[4]*16
            for i,opcode in enumerate((0xea,0x9a)):
                off,seg=struct.unpack_from('<HH',new,h[12]+4*(h[3]+i));entry=base+seg*16+off-3
                self.assertEqual(new[entry],opcode)
                target,segment=struct.unpack_from('<HH',new,entry+1)
                code=base+segment*16
                self.assertGreaterEqual(code,len(raw)+h[5]*16)
                self.assertEqual(new[code],0xe9) # fixed-width entry jump
                self.assertIn(new[code+target],(0xe9,0xeb))

    def test_scroll_keeps_pacing_and_original_acknowledgements(self):
        from full_scroll import build
        from build import ROOT
        old=(ROOT/'MAIN/DATA/ENDSCROL.TXT').read_bytes().splitlines()
        with tempfile.TemporaryDirectory() as d:
            new=build(d).read_bytes().splitlines()
        self.assertEqual(len(old),len(new))
        self.assertEqual([(i,x) for i,x in enumerate(old) if x.startswith((b'[',b'%'))],
                         [(i,x) for i,x in enumerate(new) if x.startswith((b'[',b'%'))])
        start=old.index(b'Future Crew greets the following groups:')
        closing=max(i for i,line in enumerate(old) if line==b'Second Reality')
        old[closing]=b'Robotron 1715'
        self.assertEqual(old[start:],new[start:])

    def test_full_launcher_preserves_sequence_and_pm_bridge(self):
        original=launcher();remake=launcher(robotron=True)
        self.assertIn('push    0 ; original full-demo entry',original)
        self.assertIn('mov     si,OFFSET exe23',remake)
        self.assertIn('call rt_exec32',remake)
        self.assertIn('cmp cx,18',remake)
        self.assertNotIn('mov     si,OFFSET exe2021\n        call    partexecute',remake)
        self.assertIn('mov     si,OFFSET exe2021\n        call    partexecute',original)

if __name__=='__main__':unittest.main()
