"""Validate optional chapter logs against the built musical schedule."""
import re


def verify(log, scenes):
    if not log.endswith('COMPLETE\n'):
        raise ValueError('Effect did not complete')
    entries=re.findall(r'^ENTRY scene=(\w+) order=(\d+) row=(\d+)',log,re.M)
    if len(entries)!=len(scenes):raise ValueError('Missing or duplicate chapter entries')
    result=[]
    for index,((name,order,row),scene) in enumerate(zip(entries,scenes)):
        actual=int(order)*64+int(row);target=scene['entry'][0]*64+scene['entry'][1]
        # Initial executable/asset load can consume some rows; later scenes
        # share the same process and must hit their boundary within two rows.
        if name.lower().replace('_','-')!=scene['scene'] or not 0<=actual-target<=(16 if index==0 else 2):
            raise ValueError(f'Chapter missed entry: {name} {order}:{row}')
        result.append({'scene':name.lower().replace('_','-'),'position':[int(order),int(row)]})
    end=re.search(r'^END order=(\d+) row=(\d+) frames=(\d+)',log,re.M)
    if not end:raise ValueError('Missing chapter end')
    order,row,frames=map(int,end.groups());target=scenes[-1]['exit']
    if not 0<=order*64+row-(target[0]*64+target[1])<=2:raise ValueError('Chapter missed final exit')
    if frames<30:raise ValueError('Insufficient rendered chapter frames')
    return {'entries':result,'end':[order,row],'frames':frames}
