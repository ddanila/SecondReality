"""Host-side decoder for the U2E delta animation stream (VISU/C/U2E.C)."""
import struct


def mapping(data):
    offset = struct.unpack_from('<I', data, 4)[0]
    count = struct.unpack_from('<H', data, offset)[0]
    return [0, *struct.unpack_from(f'<{count-1}H', data, offset+2)]


def decode(data, count):
    frames, records, pos, group = [], [], 0, 0
    states = [[0]*12 for _ in range(count)]
    visible = [False]*count

    def take(size, signed=False):
        nonlocal pos
        if pos+size > len(data):
            raise ValueError('Truncated animation')
        value = int.from_bytes(data[pos:pos+size], 'little', signed=signed)
        pos += size
        return value

    while pos < len(data):
        flag = take(1)
        if flag == 255:
            end = take(1)
            if end == 255:
                if records or pos != len(data):
                    raise ValueError('Unexpected animation end or trailing bytes')
                return frames
            if end > 127:
                raise ValueError('Unknown frame marker')
            frames.append((records, end))
            records, group = [], 0
            continue
        if flag & 0xc0 == 0xc0:
            group = (flag & 63)*16
            flag = take(1)
        obj = group + (flag & 15)
        if obj >= count or flag & 0xc0 == 0xc0:
            raise ValueError('Invalid animation object')
        payload_start = pos
        mask = take((flag >> 4) & 3)
        if mask > 0xffff:
            raise ValueError('Unknown animation fields')
        delta = [take((0,1,2,4)[(mask >> (2*k)) & 3], True) for k in range(3)]
        delta += [take(2 if mask & 64 else 1, True) if mask & (128 << k) else 0
                  for k in range(9)]
        states[obj] = [a+b for a,b in zip(states[obj],delta)]
        # Matrix additions wrap at 16 bits in the DOS player.
        states[obj][3:] = [(v+32768) % 65536-32768 for v in states[obj][3:]]
        if flag & 0xc0:
            visible[obj] = bool(flag & 0x80)
        records.append({'object':obj, 'flag':flag, 'payload':data[payload_start:pos],
                        'state':tuple(states[obj]), 'visible':visible[obj]})
    raise ValueError('Missing animation end')


def static_visibility(data, meshes):
    """Expose objects with constant observed poses; preserve all other records.

    Hidden moving poses cannot be recovered from this stream. Constancy is an
    inference from visible samples, appropriate for the original static city.
    """
    frames = decode(data, len(meshes))
    poses = [set() for _ in meshes]
    for records, _ in frames:
        for record in records:
            if record['visible']:
                poses[record['object']].add(record['state'])
    static = {i:next(iter(samples)) for i,samples in enumerate(poses)
              if i and meshes[i] != 28 and len(samples) == 1}
    if not static:
        raise ValueError('No static object placements found')
    output = bytearray()

    def emit(obj, flag, payload):
        # Explicit group per record avoids depending on removed records.
        output.extend(bytes((0xc0 | (obj >> 4), (flag & 0xf0) | (obj & 15))))
        output.extend(payload)

    for n, (records, fov) in enumerate(frames):
        if n == 0:
            for obj, pose in static.items():
                emit(obj, 0xa0, struct.pack('<H3i9h', 0xffff, *pose))
        for record in records:
            if record['object'] not in static:
                emit(record['object'], record['flag'], record['payload'])
        output.extend((255, fov))
    output.extend((255,255))
    return bytes(output), {'mode':'static', 'frames':len(frames),
                           'always_visible_objects':sorted(static),
                           'preserved_objects':[i for i in range(1,len(meshes)) if i not in static],
                           'bytes':len(output)}
