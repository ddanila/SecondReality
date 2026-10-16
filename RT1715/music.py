"""Read the released MUSIC0's XOR-packed S3M timing on the host.

Only the linear flight/credits introduction is needed. Reject control flow
we do not implement rather than silently producing a wrong synchronization.
"""
import struct


def timeline(path, first=18, last=28):
    data = path.read_bytes()
    orders, instruments, patterns = struct.unpack_from('<3H', data, 32)
    sequence = data[96:96+orders]
    pointers = struct.unpack_from(f'<{patterns}H', data, 96+orders+2*instruments)
    speed, tempo = data[49:51]
    time = 0.0
    result = []
    for order in range(first, last+1):
        pattern = sequence[order]
        if pattern == 254:
            continue
        if pattern == 255:
            break
        offset = pointers[pattern]*16
        size = struct.unpack_from('<H', data, offset)[0]
        packed = bytes(data[offset+i] ^ ((i ^ (i << 2)) & 255) for i in range(2, size))
        pos = 0
        for row in range(64):
            events = []
            while True:
                flags = packed[pos]; pos += 1
                if not flags:
                    break
                event = {'channel': flags & 31}
                if flags & 32:
                    event['note'], event['instrument'] = packed[pos:pos+2]; pos += 2
                if flags & 64:
                    event['volume'] = packed[pos]; pos += 1
                if flags & 128:
                    event['command'], event['argument'] = packed[pos:pos+2]; pos += 2
                events.append(event)
            finish = False
            for event in events:
                cmd, arg = event.get('command'), event.get('argument')
                if cmd == 1 and arg:
                    speed = arg
                if cmd == 20:
                    if arg < 32:
                        raise ValueError('Tempo slides are not supported')
                    tempo = arg
                if cmd == 3:
                    if arg:
                        raise ValueError('Nonzero pattern breaks are not supported')
                    finish = True
                if cmd == 2 or (cmd == 19 and arg >> 4 in (6, 11, 14)):
                    raise ValueError('Unsupported jump, loop or pattern delay')
            duration = speed*2.5/tempo
            result.append(dict(order=order, row=row, seconds=time,
                               duration=duration, events=events))
            time += duration
            if finish:
                break
    return result


def flight_header(path):
    rows = timeline(path)
    origin = next(r['seconds'] for r in rows if r['order'] == 19)
    ticks = [[0]*64 for _ in range(8)]
    for r in rows:
        if 19 <= r['order'] <= 26:
            ticks[r['order']-19][r['row']] = round((r['seconds']-origin)*100)
    return 'static unsigned rt_row_cs[8][64] = {\n' + ',\n'.join(
        '{'+','.join(map(str, row))+'}' for row in ticks) + '\n};\n'


def write_credit_schedule(module,output,transition,count):
    """Beat-aligned entries with an absolute end cue; loading cannot accumulate drift."""
    rows=timeline(module,last=43)
    begin=next(r['seconds'] for r in rows if (r['order'],r['row'])==(28,0))
    end=next(r['seconds'] for r in rows if [r['order'],r['row']]==transition['credits_end'])-begin
    candidates=[r for r in rows if r['order']>=28 and r['row']%8==0 and r['seconds']-begin<end-2]
    starts=[min(candidates,key=lambda r:abs(r['seconds']-begin-end*i/count)) for i in range(count)]
    times=[round((r['seconds']-begin)*100) for r in starts]+[round(end*100)]
    if any(b-a<200 for a,b in zip(times,times[1:])):raise ValueError('Credit cues leave too little reading time')
    lines=[str(count)];report=[]
    for i,(start,finish) in enumerate(zip(times,times[1:])):
        # Leave 120 ms for the next file read, keeping its entrance on the beat.
        stop=finish if i==count-1 else finish-12
        enter=start+round(transition['entry_seconds']*100)
        leave=stop-round(transition['exit_seconds']*100)
        if enter>=leave:raise ValueError('Credit transitions overlap')
        lines.append(f'{start} {enter} {leave} {stop}')
        report.append(dict(card=i+1,order=starts[i]['order'],row=starts[i]['row'],start_cs=start,enter_end_cs=enter,exit_start_cs=leave,end_cs=stop))
    output.mkdir(parents=True,exist_ok=True)
    (output/'CRED.CUE').write_text('\n'.join(lines)+'\n')
    clock=[[0]*64 for _ in range(16)]
    for r in rows:
        if 28<=r['order']<=43:clock[r['order']-28][r['row']]=round((r['seconds']-begin)*100)
    (output/'CRED.TIM').write_bytes(struct.pack('<1024H',*(t for row in clock for t in row)))
    import json
    (output/'credit-cues.json').write_text(json.dumps(report,indent=2)+'\n')


def module_archive(module0, module1=None):
    """Build STARTMUS's two-slot archive without modifying module payloads.

    A one-module cut aliases slot 1 to slot 0, matching the original extraction.
    Supplying module 1 prepares the original loader format for future chapters;
    choosing playback orders and switching modules remains the launcher's job.
    """
    for payload in (module0,) if module1 is None else (module0, module1):
        if len(payload) < 96 or payload[44:48] != b'SCRM':
            raise ValueError('Expected an S3M module payload')
    second = 16 if module1 is None else 16 + len(module0)
    return struct.pack('<II6xH', 16, second, 0x1B1C) + module0 + (module1 or b'')
