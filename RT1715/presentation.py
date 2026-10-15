"""One validated entry point for Robotron sources, motion, materials and cards."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from PIL import ImageFont
from prepare import printable

HERE=Path(__file__).resolve().parent
DEFAULT=HERE/'assets/robotron/presentation.json'


def load(path=DEFAULT, source=None):
    path=Path(path).resolve();config=json.loads(path.read_text())
    allowed={'version','source','flight','credits','materials','models','transition'}
    if config.get('version')!=1 or set(config)-allowed:raise ValueError('Invalid presentation manifest')
    root=Path(source).resolve() if source else (path.parent/config['source']).resolve()
    if not (root/'model.scad').is_file() or not (root/'browser/model.json').is_file():
        raise ValueError('Source needs model.scad and browser/model.json')
    files={k:(path.parent/config[k]).resolve() for k in ('flight','credits','materials')}
    for file in files.values():
        if not file.is_file():raise ValueError(f'Missing presentation input: {file}')
    flight=json.loads(files['flight'].read_text());cards=json.loads(files['credits'].read_text())
    if flight['fps']!=35 or flight['frames']!=2031:raise ValueError('Keep the authored 35 Hz music interval (2031 frames)')
    for key,field in [('keyframes','eye'),('drone','position')]:
        track=flight[key]
        if track[0]['time']!=0 or any(a['time']>=b['time'] for a,b in zip(track,track[1:])):
            raise ValueError('Motion times must increase from zero')
        if track[-1]['time']<(flight['frames']-1)/flight['fps']:raise ValueError('Motion ends too early')
    follow=flight.get('follow')
    if follow and not (0<=follow['weight']<=1 and 0<=follow['fade_start']<follow['end']<=45.5):
        raise ValueError('Invalid camera-follow interval')
    steering=flight.get('steering')
    if steering and not (0<=steering['lead_seconds']<=1 and 0<=steering['fade_start']<steering['end']<=45):
        raise ValueError('Steering anticipation must finish before the swoosh')
    miniature=flight.get('miniature')
    if miniature and not (0<miniature['scale']<=1 and 0<=miniature['start']<miniature['end']<=19):
        raise ValueError('Miniature drone must regain full size before the drive pass')
    machine=flight.get('machine')
    if machine:
        start,end=machine['insert'];close_start,close_end=machine['close']
        if machine['drive'] not in (0,1) or not 0<machine['withdraw_mm']<=133.35:
            raise ValueError('Invalid animated drive or disk withdrawal')
        if not 0<=start<end<=close_start<close_end<machine['ready']<45.5:
            raise ValueError('Disk must seat before lever closure and boot completion')
        if not .5<=machine.get('font_unit',.95)<=1.5:raise ValueError('Invalid CRT font size')
        if not machine['boot_lines']:raise ValueError('Boot sequence needs text')
        for line in machine['boot_lines']:
            printable([line['text']])
            if not line['text'].strip() or not close_end<=line['time']<45.5:
                raise ValueError('Boot text must follow drive closure')
            if line.get('until',58)<=line['time']:
                raise ValueError('Boot line expiry must follow its appearance')
    turn=flight.get('turntable')
    if turn and not (48.1<=turn['start']<turn['end']<=58 and 0<turn['degrees']<=180
                     and len(turn['pivot'])==3 and all(isinstance(v,(int,float)) for v in turn['pivot'])):
        raise ValueError('Turntable must follow the drone flyby and finish before credits')
    if len(cards)!=21:raise ValueError('Keep 21 cards for the music interval')
    names=set()
    source_data=json.loads((root/'browser/model.json').read_text())
    parts={part['name'] for part in source_data['parts']}
    for card in cards:
        if set(card)-{'image','lines','view','photo','render_model','evidence'}:raise ValueError('Unknown credit option')
        name=card.get('image','')
        if not re.fullmatch('[a-z0-9-]+',name) or name in names:raise ValueError('Credit image IDs must be unique safe names')
        names.add(name);printable(card['lines'])
        for line in card['lines']:
            if ImageFont.load_default(size=16).getlength(line)>304:
                raise ValueError(f'Credit text too small at DOS resolution: {name}: {line}')
        if 'view' in card:
            for prefix in card['view']['parts']:
                if not any(n==prefix or n.startswith(prefix+'-') for n in parts):raise ValueError(f'Missing model parts: {prefix}')
            for name in card['view'].get('focus_parts',[]):
                if name not in parts:raise ValueError(f'Missing focus part: {name}')
        kinds=[k for k in ('view','photo','render_model') if k in card]
        if len(kinds)!=1:raise ValueError(f'{name}: choose view, photo or render_model')
        for key in ('photo','render_model'):
            if key in card and not (files['credits'].parent/card[key]).is_file():raise ValueError(f'Missing {key}: {card[key]}')
    overrides=set()
    for model in config.get('models',[]):
        if set(model)-{'name','scad','material'} or not model.get('name') or model['name'] in ('drone','s01'):
            raise ValueError('Invalid model override; original drone is protected')
        if model['name'] in overrides:raise ValueError('Duplicate model override')
        overrides.add(model['name'])
        if not str(model.get('scad','')).lower().endswith('.scad'):raise ValueError('Replacement models must be OpenSCAD sources')
        if not (path.parent/model['scad']).is_file():raise ValueError(f'Missing OpenSCAD source: {model["scad"]}')
    materials=json.loads(files['materials'].read_text())
    expected={'dark':32,'paint':48,'pcb':64,'metal':80,'black':96,'red':112,'blue':128,'white':144}
    if set(materials)!=set(expected):raise ValueError('Keep the eight reserved material ramps')
    for name,ramp in materials.items():
        if ramp['base']!=expected[name] or not re.fullmatch('#[0-9a-fA-F]{6}',ramp['rgb']):raise ValueError('Invalid material ramp')
        if not 0<=ramp['ambient']<=1 or not 0<=ramp['diffuse']<=1-ramp['ambient']+1e-9:raise ValueError('Invalid material brightness')
    transition=config['transition']
    if not .3<=transition['entry_seconds']<=1.5 or not .2<=transition['exit_seconds']<=.8:raise ValueError('Invalid transition duration')
    if transition['credits_end']!=[43,29] or not 0<transition['flight_fade_seconds']<=1.5:
        raise ValueError('Keep credit end cue 43:29 and a short reveal fade')
    return config,root,files


def snapshot(source,destination):
    """Copy current local edits read-only, checking source stability around copy."""
    source=Path(source);destination=Path(destination)
    def stamps(root):
        paths=[*root.rglob('*.scad'),root/'browser/model.json']
        return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before=stamps(source)
    destination.mkdir(parents=True,exist_ok=True)
    shutil.copytree(source,destination,dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('*.zip','reference','downloads','checks'))
    if before!=stamps(source) or before!=stamps(destination):
        raise ValueError('Model sources changed during snapshot; run again for a consistent copy')
    (destination/'snapshot.json').write_text(json.dumps({'source':str(source),'hashes':before},indent=2)+'\n')
    return destination


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('manifest',type=Path,nargs='?',default=DEFAULT)
    args=parser.parse_args();config,root,files=load(args.manifest)
    print(f'PASS: sources, 21 readable ASCII cards, motion, materials and protected cue constraints: {args.manifest}')
