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
