#!/usr/bin/env python3
"""Export separate continuous-run comparisons with an explicit review index."""
import argparse,json
from pathlib import Path
from full_compare import compare

LABELS={'ALKU.EXE':'opening','U2A.EXE':'diskette-flight','PAM.EXE':'explosion','BEGLOGO.EXE':'title','GLENZ.EXE':'keycap','TUNNELI.EXE':'cable','TECHNO.EXE':'interference-and-monster','PANICEND.EXE':'monster-transition','MNTSCRL.EXE':'water','LNS&ZOOM.EXE':'die-lens','PLZPART.EXE':'plasma-and-chip','MINVBALL.EXE':'dots','RAYSCRL.EXE':'tape-reflections','3DSINFLD.EXE':'pcb-landscape','JPLOGO.EXE':'unicorn','U2E.EXE':'robotron-flyover','CRED.EXE':'technical-credits','ENDSCRL.EXE':'final-scroll'}


def build(original,remake,output,only=None):
    original,remake,output=map(Path,(original,remake,output));output.mkdir(parents=True,exist_ok=True)
    for capture in (original,remake):
        if json.loads((capture/'result.json').read_text())['dos_exit']!='PASS':
            raise ValueError('Review requires completed successful captures')
    records=json.loads((original/'scenes.json').read_text())
    scenes=[(a,b) for a,b in zip(records[::2],records[1::2])]
    previous=json.loads((output/'index.json').read_text()) if only and (output/'index.json').exists() else []
    index=[row for row in previous if row['part'] not in (only or [])]
    remake_records=json.loads((remake/'scenes.json').read_text())
    remake_exits={row['executable']:row for row in remake_records if row['phase']=='exit'}
    for i,(a,b) in enumerate(scenes):
        name=a['executable']
        if name=='ENDLOGO.EXE':continue
        label=LABELS[name]
        if only and label not in only:continue
        if name=='U2E.EXE':b=scenes[i+1][1] # reviewed flyover includes title interval
        # 70.086 Hz is the VGA retrace time base; retain a little context.
        start=max(0,a['retrace']/70.086-.3);duration=(b['retrace']-a['retrace'])/70.086+.6
        target=output/f'{i+1:02}-{label}.mp4'
        try:
            report=compare(original,remake,target,start,duration)
            actual=remake_exits.get(name)
            timing=None
            if actual:
                timing={'original_exit':{k:b[k] for k in ('module','order','row')},
                        'remake_exit':{k:actual[k] for k in ('module','order','row')},
                        'copper_tick_difference_after_audio_alignment':round(actual['retrace']-b['retrace']-report['remake_offset']*70.086,3)}
            index.append({'part':label,'video':target.name,'status':'ready for visual review','alignment':report,'scene_timing':timing})
        except ValueError as error:
            index.append({'part':label,'status':'sync validation failed','error':str(error)})
        index.sort(key=lambda row:list(LABELS.values()).index(row['part']))
        (output/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    rows=['<html><head><meta charset="utf-8"><title>Robotron demo review</title></head><body style="background:#101713;color:#ddd;font:18px sans-serif">', '<h1>Robotron 1715 / scene review</h1><p>Original on the left; remake on the right. One original soundtrack. Drafts await your review.</p><p>Timing details include diagnostic copper-interrupt counts; these can lose counts while the protected renderer masks interrupts. Tracker cues and measured audio offsets establish synchronization.</p>']
    import html
    for row in index:
        rows.append('<h2>'+html.escape(row['part'])+'</h2><p>'+html.escape(row['status'])+'</p>')
        if 'video' in row:rows.append('<video controls preload="none" width="960" src="'+row['video']+'"></video>')
        else:rows.append('<pre>'+html.escape(row['error'])+'</pre>')
        if row.get('scene_timing'):rows.append('<details><summary>Timing measurements</summary><pre>'+html.escape(json.dumps(row['scene_timing'],indent=2))+'</pre></details>')
    (output/'index.html').write_text('\n'.join(rows)+'</body></html>')
    return index

def update_scene(original,remake,output,label,remake_start,alignment_window=None):
    """Replace one review from an independently captured matching music cue."""
    original,remake,output=map(Path,(original,remake,output))
    if json.loads((remake/'result.json').read_text())['dos_exit']!='PASS':
        raise ValueError('Independent review requires successful DOS capture')
    index=json.loads((output/'index.json').read_text())
    row=next(r for r in index if r['part']==label)
    previous=row['alignment']
    row['alignment']=compare(original,remake,output/row['video'],previous['reference_start'],previous['duration'],remake_start=remake_start,alignment_window=alignment_window)
    row['status']='Updated; music-aligned independent scene capture'
    row['scene_timing']={'validation':'Independent scene playback at its original music cue; not an uninterrupted full run.'}
    if (remake/'scenes.json').exists():
        exits=[r for r in json.loads((remake/'scenes.json').read_text()) if r['phase']=='exit']
        row['scene_timing']['tracker_exits']=[{k:r[k] for k in ('executable','module','order','row')} for r in exits]
    (output/'index.json').write_text(json.dumps(index,indent=2)+'\n')
    build(original,original,output,only=['_refresh_html_'])
    return row


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('original');p.add_argument('remake');p.add_argument('output');p.add_argument('--only',nargs='+');a=p.parse_args();build(a.original,a.remake,a.output,a.only)
