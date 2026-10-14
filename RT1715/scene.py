"""Second Reality VERS/NAME/VERT/NORM/POLY/ORD geometry, from VISU/C/SAVE.C.

Coordinates are Z-up. Animation references are preserved by replacing whole
numbered mesh slots and retaining their names. Visibility rewriting lives
in animation.py; mesh conversion itself does not alter animation.
"""
import itertools
import math
from pathlib import Path
import struct

DRONE_SLOT = 28  # "s01"; also special-cased in VISU/C/U2E.C
MAX_FACES = 500
MAX_VERTICES = 500  # Includes center and optional eight sorting probes.


def blocks(data):
    result = []
    pos = 0
    while pos < len(data):
        if pos + 8 > len(data):
            raise ValueError("Truncated scene block header")
        tag, length = struct.unpack_from("<4sI", data, pos)
        pos += 8
        if length % 4 or pos + length > len(data):
            raise ValueError("Invalid scene block length")
        result.append((tag, data[pos:pos + length]))
        pos += length
        if tag == b"END ":
            if pos != len(data):
                raise ValueError("Trailing scene data")
            return result
    raise ValueError("Missing END block")


def decode(data):
    chunks = dict(blocks(data))
    if struct.unpack_from("<H", chunks[b"VERS"])[0] != 0x100:
        raise ValueError("Unsupported mesh version")
    count = struct.unpack_from("<H", chunks[b"VERT"])[0]
    vertices = [struct.unpack_from("<iii", chunks[b"VERT"], 4 + i * 16)
                for i in range(count)]
    order = chunks[b"ORD0"]
    words = struct.unpack_from("<H", order)[0]
    faces = []
    for offset in struct.unpack_from(f"<{words - 3}H", order, 4):
        flags, color, normal = struct.unpack_from("<HHH", chunks[b"POLY"], offset)
        face = struct.unpack_from(f"<{flags & 255}H", chunks[b"POLY"], offset + 6)
        if any(v >= count for v in face):
            raise ValueError("Invalid mesh vertex index")
        faces.append({"indices": face, "color": color, "flags": flags & 0xff00})
    used = sorted({i for face in faces for i in face["indices"]})
    bounds = [[min(vertices[i][k] for i in used), max(vertices[i][k] for i in used)]
              for k in range(3)]
    return {"name": chunks[b"NAME"].split(b"\0")[0].decode("ascii"),
            "vertices": vertices, "faces": faces, "bounds": bounds}


def inventory(root):
    output = []
    for slot in range(1, 43):
        mesh = decode((root / f"U2E.{slot:03}").read_bytes())
        output.append({"slot": slot, "name": mesh["name"], "bounds": mesh["bounds"],
                       "vertices": len(mesh["vertices"]), "faces": len(mesh["faces"]),
                       "protected": slot == DRONE_SLOT})
    return output


def read_stl(path):
    """Read OpenSCAD's explicitly requested binary STL, ignoring stored normals."""
    data = Path(path).read_bytes()
    if len(data) < 84:
        raise ValueError("Truncated binary STL")
    count = struct.unpack_from("<I", data, 80)[0]
    if len(data) != 84 + count * 50 or not 0 < count <= MAX_FACES:
        raise ValueError(f"STL must contain 1..{MAX_FACES} triangles; simplify the SCAD / lower $fn")
    triangles = []
    for i in range(count):
        xyz = struct.unpack_from("<9f", data, 84 + i * 50 + 12)
        if not all(math.isfinite(v) for v in xyz):
            raise ValueError("Non-finite STL coordinate")
        triangles.append([tuple(xyz[j:j + 3]) for j in (0, 3, 6)])
    return triangles


def fit_mesh(triangles, bounds, rotate_z=0):
    """Uniform fit inside the original mesh bounds, centered XY and grounded Z."""
    angle = math.radians(rotate_z)
    c, s = math.cos(angle), math.sin(angle)
    rotated = [[(c*x-s*y, s*x+c*y, z) for x, y, z in face] for face in triangles]
    lo = [min(v[k] for f in rotated for v in f) for k in range(3)]
    hi = [max(v[k] for f in rotated for v in f) for k in range(3)]
    if any(hi[k] - lo[k] < 1e-8 for k in range(3)):
        raise ValueError("Replacement must have nonzero width, depth and height")
    scale = min((bounds[k][1] - bounds[k][0]) / (hi[k] - lo[k]) for k in range(3))
    center = [(lo[k] + hi[k]) / 2 for k in range(3)]
    origin = [(bounds[k][0] + bounds[k][1]) / 2 for k in range(3)]
    center[2], origin[2] = lo[2], bounds[2][0]
    return [[tuple(round((v[k] - center[k])*scale + origin[k]) for k in range(3))
             for v in face] for face in rotated]


def chunk(tag, data):
    data += bytes((-len(data)) % 4)
    return tag + struct.pack("<I", len(data)) + data


def encode(name, triangles, color=64, shades=32, face_colors=None, precomputed_orders=True, sort_center=None, smooth=False):
    if shades not in (1, 8, 16, 32) or not 0 <= color <= 251 or color + shades > 252:
        raise ValueError("Material must fit palette entries 0..251, with 1/8/16/32 shades")
    if not 0 < len(triangles) <= MAX_FACES:
        raise ValueError("Too many triangles")
    if face_colors is None: face_colors=[color]*len(triangles)
    if len(face_colors)!=len(triangles) or any(not isinstance(c,int) or c<0 or c+shades>252 for c in face_colors):
        raise ValueError("Face colors must match the polygon count and fit the palette")
    vertices, faces, normals, mapping = [], [], [], {}
    normal_ids, normal_mapping = [], {}
    for tri in triangles:
        ids = []
        for point in tri:
            if len(point) != 3 or any(not isinstance(v, int) or abs(v) > 1000000 for v in point):
                raise ValueError("Invalid or excessive scene coordinate")
            if point not in mapping:
                mapping[point] = len(vertices)
                vertices.append(point)
            ids.append(mapping[point])
        if not 3 <= len(tri) <= 4:
            raise ValueError("Expected triangles or convex quads")
        a, b, c = tri[:3]
        u, v = [b[k]-a[k] for k in range(3)], [c[k]-a[k] for k in range(3)]
        n = (u[1]*v[2]-u[2]*v[1], u[2]*v[0]-u[0]*v[2], u[0]*v[1]-u[1]*v[0])
        length = math.sqrt(sum(x*x for x in n))
        if length == 0:
            raise ValueError("Triangle collapsed after scene scaling; simplify or enlarge the model")
        normal = tuple(round(x * 16384 / length) for x in n)
        if normal not in normal_mapping:
            normal_mapping[normal] = len(normals)
            normals.append(normal)
        normal_ids.append(normal_mapping[normal])
        faces.append(ids)
    if len(vertices) + (9 if precomputed_orders else 1) > MAX_VERTICES:
        raise ValueError(f"Mesh exceeds {MAX_VERTICES - (9 if precomputed_orders else 1)} geometry vertices")
    center = tuple(round(sum(p[k] for p in vertices) / len(vertices)) for k in range(3))
    if sort_center is not None:
        if len(sort_center)!=3 or any(not isinstance(v,int) or abs(v)>1000000 for v in sort_center):
            raise ValueError("Invalid sorting center")
        center=tuple(sort_center)
    center_id = len(vertices)
    vertices.append(center)
    directions = list(itertools.product((-1, 1), repeat=3)) if precomputed_orders else []
    for direction in directions:
        vertices.append(tuple(center[k] + direction[k]*256 for k in range(3)))
    vertex_normals=[-1]*len(vertices)
    if smooth:
        sums=[[0.,0.,0.] for _ in vertices]
        for face,ni in zip(faces,normal_ids):
            for index in face:
                for axis in range(3):sums[index][axis]+=normals[ni][axis]
        for index,total in enumerate(sums):
            length=math.sqrt(sum(v*v for v in total))
            if not length:continue
            vertex_normals[index]=len(normals)
            normals.append(tuple(round(v*16384/length) for v in total))
        if len(normals)>500:raise ValueError('Smooth surface exceeds 500 normals')
    vertex_data = struct.pack('<HH', len(vertices), 0)
    vertex_data += b''.join(struct.pack('<iiihH', *p, vertex_normals[i], 0xfc) for i,p in enumerate(vertices))
    normal_data = struct.pack("<HH", len(normals), len(normals))
    normal_data += b"".join(struct.pack("<hhhH", *n, 0xfc) for n in normals)
    flags = {1: 0, 8: 0x400, 16: 0x800, 32: 0xc00}[shades]
    if smooth:flags |= 0x1000
    poly, offsets = bytearray(b"\0\0"), []
    for i, face in enumerate(faces):
        offsets.append(len(poly))
        poly.extend(struct.pack(f"<{3+len(face)}H", len(face) | flags, face_colors[i], normal_ids[i], *face))

    def order(probe, ids):
        return struct.pack(f"<{len(ids)+3}H", len(ids)+3, probe, *(offsets[i] for i in ids), 0)

    result = chunk(b"VERS", struct.pack("<H", 0x100))
    result += chunk(b"NAME", name.encode("ascii") + b"\0")
    result += chunk(b"VERT", vertex_data) + chunk(b"NORM", normal_data) + chunk(b"POLY", bytes(poly))
    result += chunk(b"ORD0", order(center_id, list(range(len(faces)))))
    # Like the original OSORT.C, choose one of eight precomputed painter orders
    # by the nearest transformed probe. No z-buffer: avoid interpenetrating parts.
    for i, direction in enumerate(directions):
        ids = sorted(range(len(faces)), key=lambda f: min(
            sum(vertices[v][k]*direction[k] for k in range(3)) for v in faces[f]))
        result += chunk(b"ORDE", order(center_id + i + 1, ids))
    result += chunk(b"END ", b"")
    if len(result) >= 64000:
        raise ValueError("Mesh exceeds the 16-bit object-file budget")
    return result
