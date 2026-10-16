"""Host-side chapter contracts and tracker-cue validation.

Contracts describe executable scenes; they do not generate a DOS launcher.
Unimplemented cuts must never silently fall back to the short cut.
"""
import argparse
import json
from pathlib import Path
import re

DEFAULT = Path(__file__).resolve().parent / 'assets/robotron/chapters.json'


def position(value):
    if (not isinstance(value, list) or len(value) != 2 or
            any(type(v) is not int for v in value) or
            not 0 <= value[0] <= 255 or not 0 <= value[1] < 64):
        raise ValueError(f'Invalid tracker position: {value!r}')
    return tuple(value)


def load(path=DEFAULT, cut='short'):
    document = json.loads(Path(path).read_text())
    if document.get('version') != 1:
        raise ValueError('Unsupported chapter contract version')
    if cut not in document['cuts']:
        raise ValueError(f'Unknown cut: {cut}')
    selected = document['cuts'][cut]
    scenes = selected['scenes']
    if not scenes or len(set(scenes)) != len(scenes):
        raise ValueError('A cut needs unique scene IDs')
    for name in scenes:
        scene = document['scenes'][name]
        if scene['module'] not in document['modules']:
            raise ValueError(f'Unknown music module for {name}')
        if position(scene['entry']) >= position(scene['exit']):
            raise ValueError(f'Reversed scene interval: {name}')
        if not scene.get('state_contract'):
            raise ValueError(f'Missing state contract: {name}')
    for name, cue in selected['checks'].items():
        if cue['scene'] not in scenes:
            raise ValueError(f'Cue outside cut: {name}')
        low, high = position(cue['min']), position(cue['max'])
        if not low <= position(cue['target']) <= high:
            raise ValueError(f'Invalid cue window: {name}')
        if not re.fullmatch(r'[A-Z_]+', cue['label']):
            raise ValueError(f'Invalid log label: {name}')
    return document, selected


def verify_logs(logs, path=DEFAULT, cut='short'):
    """Validate scene-keyed logs; positions remain local to each music module."""
    _, selected = load(path, cut)
    result = {}
    for name, cue in selected['checks'].items():
        matches = re.findall(r'^' + cue['label'] + r'\b[^\n]*order=(\d+) row=(\d+)',
                             logs.get(cue['scene'], ''), re.M)
        if len(matches) != 1:
            raise ValueError(f'Expected exactly one {name} cue, found {len(matches)}')
        actual = position(list(map(int, matches[0])))
        if not position(cue['min']) <= actual <= position(cue['max']):
            raise ValueError(f'{name} missed music cue: {actual}')
        result[name] = actual
    return result


def require_buildable(path=DEFAULT, cut='short'):
    document, selected = load(path, cut)
    if selected.get('launcher') != 'short-v1' or selected['scenes'] != ['flight', 'credits']:
        raise ValueError(f'Cut has no implemented launcher: {cut}')
    # The current assembly launcher is fixed. A manifest edit must not pretend
    # that it changed executable dispatch or module loading in that binary.
    expected = {'flight': ('U2E.EXE', 'music0', [18, 0]),
                'credits': ('CRED.EXE', 'music0', [28, 0])}
    for name, (executable, module, entry) in expected.items():
        scene = document['scenes'][name]
        if (scene['executable'], scene['module'], scene['entry']) != (executable, module, entry):
            raise ValueError(f'Contract needs a new launcher adapter: {name}')
    if any(document['scenes'][name]['status'] != 'implemented' for name in selected['scenes']):
        raise ValueError(f'Cut contains unimplemented scenes: {cut}')
    return document, selected


def cue_sheet(path=DEFAULT, cut='short', root=None):
    """Derive scene-relative cue times, never capture-global video offsets.

    Uses the deliberately strict S3M timing reader. Unsupported control flow
    remains an error until its playback semantics have been implemented.
    """
    from music import timeline
    document, selected = load(path, cut)
    root = Path(root) if root else Path(__file__).resolve().parent.parent
    result = []
    for name in selected['scenes']:
        scene = document['scenes'][name]
        entry, end = position(scene['entry']), position(scene['exit'])
        # Timing starts at the module's first scene, retaining tempo changes
        # through subsequent scenes on that same uninterrupted module.
        first = min(position(document['scenes'][n]['entry'])[0]
                    for n in selected['scenes']
                    if document['scenes'][n]['module'] == scene['module'])
        module = document['modules'][scene['module']]['source']
        rows = timeline(root/module, first=first, last=end[0])
        times = {(r['order'], r['row']): r['seconds'] for r in rows}
        if entry not in times or end not in times:
            raise ValueError(f'Unreachable scene boundary: {name}')
        cues = {}
        for key, cue in selected['checks'].items():
            if cue['scene'] == name:
                target = position(cue['target'])
                if target not in times:
                    raise ValueError(f'Unreachable cue: {key}')
                cues[key] = round(times[target] - times[entry], 6)
        result.append({'scene': name, 'module': scene['module'],
                       'entry': list(entry), 'exit': list(end),
                       'seconds': round(times[end]-times[entry], 6),
                       'cue_seconds_from_scene_entry': cues})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=DEFAULT)
    parser.add_argument('--cut', default='short')
    parser.add_argument('--timing', action='store_true', help='Derive scene-relative cue times from source modules')
    parser.add_argument('--capture', type=Path, help='Validate existing capture logs without DOS playback')
    args = parser.parse_args()
    document, selected = load(args.manifest, args.cut)
    report = {'cut': args.cut, 'scenes': selected['scenes'], 'contracts': {
        name: document['scenes'][name] for name in selected['scenes']}}
    if args.timing:
        report['cue_sheet'] = cue_sheet(args.manifest, args.cut)
    if args.capture:
        logs = {name: (args.capture / document['scenes'][name]['capture_log']).read_text()
                for name in selected['scenes']}
        report['verified_cues'] = verify_logs(logs, args.manifest, args.cut)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
