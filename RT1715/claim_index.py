"""Validate and export the curated, portable technical-credit evidence index."""
import argparse,hashlib,json
from pathlib import Path

HERE=Path(__file__).resolve().parent
DEFAULT=HERE/'assets/robotron/claims.json'


def validate(index=DEFAULT,credits=None,source_root=None):
    data=json.loads(Path(index).read_text())
    cards=json.loads(Path(credits or HERE/'assets/robotron/credits.json').read_text())
    expected={(c['image'],i):line for c in cards for i,line in enumerate(c['lines'],1) if line}
    found={}
    kinds={'editorial','specimen-observation','reference-configuration','documented-design','functional-explanation','model-reconstruction'}
    for claim in data['claims']:
        key=(claim['card'],claim['line'])
        if key in found or claim['kind'] not in kinds:raise ValueError('Invalid/duplicate claim: '+str(key))
        found[key]=claim['text']
        if claim['kind']!='editorial' and not claim['sources']:raise ValueError('Missing claim evidence: '+str(key))
        for name in claim['sources']:
            if name not in data['sources']:raise ValueError('Unknown evidence ID: '+name)
    if found!=expected:raise ValueError('Credit text changed: review the claim index before publishing')
    for name,source in data['sources'].items():
        if not source.get('excerpt') or not source.get('locator'):raise ValueError('Incomplete portable evidence: '+name)
        if source_root:
            path=Path(source_root)/source['path']
            if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:
                raise ValueError('Evidence source changed; review '+source['path'])
    return data


def export(destination,index=DEFAULT,credits=None):
    data=validate(index,credits);destination=Path(destination);destination.mkdir(parents=True,exist_ok=True)
    (destination/'CLAIMS.JSON').write_text(json.dumps(data,indent=2)+'\n')
    lines=['ROBOTRON 1715M - TECHNICAL CLAIM INDEX','',
           'Specimen observations and reference configurations are distinguished below.',
           'Short source excerpts, exact locations and file hashes travel with this index.',
           'Source paths identify the development repositories; reading this index needs neither repository.','']
    for note in data['presentation_notes']:lines.extend([note,''])
    for claim in data['claims']:
        lines.extend([f"{claim['card']} / line {claim['line']}: {claim['text']}",
                      '  Classification: '+claim['kind'],'  Evidence: '+(', '.join(claim['sources']) or 'Editorial text')])
        if claim.get('qualification'):lines.append('  Scope: '+claim['qualification'])
    lines+=['','SOURCE LOCATORS','']
    for name,source in data['sources'].items():
        lines.extend([name, '  '+source['path'], '  '+source['locator'],
                      '  SHA-256: '+source['sha256'],'  Excerpt: '+source['excerpt'],''])
    (destination/'TECHNICAL-SOURCES.TXT').write_text('\n'.join(lines)+'\n')
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check-source',type=Path)
    p.add_argument('--output',type=Path);a=p.parse_args()
    data=validate(source_root=a.check_source)
    if a.output:export(a.output)
    print(f"PASS: {len(data['claims'])} credit lines, {len(data['sources'])} precise source records")
