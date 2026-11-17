"""Exact garment-piece masks from a model's own UV islands (reads the model from your game files)."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bntx_astc as bx
POOL = 94208
_ISLANDS = {}
_MASKS = {}
_FIELDS = {}

def _pool(b):
    r = b.rfind(b'_RLT')
    return struct.unpack_from('<I', b, r + 48)[0] if r >= 0 else POOL

def edge_field(rel, shape, w, h):
    key = ('edge', rel, shape, w, h)
    if key in _FIELDS:
        return _FIELDS[key]
    hf = height_field(rel, shape, w, h)
    f = [None] * (w * h)
    for x in range(w):
        rows = [y for y in range(h) if hf[y * w + x] is not None]
        if not rows:
            continue
        top, bot = (min(rows), max(rows))
        for y in rows:
            f[y * w + x] = (bot - y) / max(1, bot - top)
    _FIELDS[key] = f
    return f

def height_field(rel, shape, w, h):
    key = (rel, shape, w, h)
    if key in _FIELDS:
        return _FIELDS[key]
    b = bx.load(rel)[0]
    pool = _pool(b)
    u64 = lambda o: struct.unpack_from('<Q', b, o)[0]
    u32 = lambda o: struct.unpack_from('<I', b, o)[0]
    u16 = lambda o: struct.unpack_from('<H', b, o)[0]

    def rs(o):
        n = u16(o)
        return b[o + 2:o + 2 + n].decode('latin1')
    i = b.find(b'FSHP')
    while i >= 0 and rs(u64(i + 8)) != shape:
        i = b.find(b'FSHP', i + 4)
    assert i >= 0, shape
    fv, mesh = (u64(i + 16), u64(i + 24))
    attr, na = (u64(fv + 8), b[fv + 76])
    stride, base, vc = (u32(u64(fv + 56)), pool + u32(fv + 72), u32(fv + 80))
    at = {rs(u64(attr + k * 16)): (u32(attr + k * 16 + 8), u16(attr + k * 16 + 12)) for k in range(na)}
    assert at['_p0'][0] == 6149 and at['_u0'][0] == 4609, at
    ys = [struct.unpack_from('<f', b, base + v * stride + at['_p0'][1] + 4)[0] for v in range(vc)]
    uvs = [tuple((c / 65535 for c in struct.unpack_from('<2H', b, base + v * stride + at['_u0'][1]))) for v in range(vc)]
    lo, hi = (min(ys), max(ys))
    cnt = u32(mesh + 44)
    idx = struct.unpack_from(f'<{cnt}H', b, pool + u32(mesh + 32))
    f = [None] * (w * h)
    for t in range(0, cnt - 2, 3):
        a, c, d = idx[t:t + 3]
        (x0, y0), (x1, y1), (x2, y2) = [(uvs[k][0] * w, uvs[k][1] * h) for k in (a, c, d)]
        q0, q1, q2 = [(ys[k] - lo) / (hi - lo) for k in (a, c, d)]
        area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
        if area == 0:
            continue
        for py in range(max(0, int(min(y0, y1, y2))), min(h - 1, int(max(y0, y1, y2))) + 1):
            cy = py + 0.5
            for px in range(max(0, int(min(x0, x1, x2))), min(w - 1, int(max(x0, x1, x2))) + 1):
                cx = px + 0.5
                l1 = ((cx - x0) * (y2 - y0) - (x2 - x0) * (cy - y0)) / area
                l2 = ((x1 - x0) * (cy - y0) - (cx - x0) * (y1 - y0)) / area
                l0 = 1 - l1 - l2
                if l0 >= 0 and l1 >= 0 and (l2 >= 0):
                    f[py * w + px] = l0 * q0 + l1 * q1 + l2 * q2
    _FIELDS[key] = f
    return f

def _model_islands(rel):
    if rel in _ISLANDS:
        return _ISLANDS[rel]
    b = bx.load(rel)[0]
    u64 = lambda o: struct.unpack_from('<Q', b, o)[0]
    u32 = lambda o: struct.unpack_from('<I', b, o)[0]
    u16 = lambda o: struct.unpack_from('<H', b, o)[0]

    def rs(o):
        if not 0 < o < len(b) - 2:
            return None
        n = u16(o)
        s = b[o + 2:o + 2 + n]
        return s.decode('latin1') if n and len(s) == n else None

    def all_at(magic):
        out, i = ([], b.find(magic))
        while i >= 0:
            out.append(i)
            i = b.find(magic, i + 4)
        return out
    mats = {}
    for i in all_at(b'FMAT'):
        nm, arr = (rs(u64(i + 8)), u64(i + 32))
        tex = rs(u64(arr)) if arr < len(b) else None
        if nm and tex:
            mats[nm] = tex
    out = []
    for s in all_at(b'FSHP'):
        name = rs(u64(s + 8))
        fv, mesh = (u64(s + 16), u64(s + 24))
        fmt, cnt, ioff = (u32(mesh + 40), u32(mesh + 44), u32(mesh + 32))
        assert fmt == 1, (name, fmt)
        idx = struct.unpack_from(f'<{cnt}H', b, POOL + ioff)
        tex = mats.get(name.split('__', 1)[1]) if '__' in name else None
        attr, na = (u64(fv + 8), b[fv + 76])
        uv = None
        for k in range(na):
            o = attr + k * 16
            if rs(u64(o)) == '_u0':
                ufmt, uoff = (u32(o + 8), u16(o + 12))
                stride, base, vc = (u32(u64(fv + 56)), POOL + u32(fv + 72), u32(fv + 80))
                uv = []
                for v in range(vc):
                    p = base + v * stride + uoff
                    if ufmt == 4609:
                        a, c = struct.unpack_from('<2H', b, p)
                        uv.append((a / 65535, c / 65535))
                    elif ufmt == 4613:
                        uv.append(struct.unpack_from('<2e', b, p))
                    elif ufmt == 5893:
                        uv.append(struct.unpack_from('<2f', b, p))
                    else:
                        raise ValueError(f'UV format {ufmt:#x}')
                break
        tris = [idx[i:i + 3] for i in range(0, cnt - 2, 3)]
        parent = {}

        def find(a):
            while parent.setdefault(a, a) != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for t in tris:
            for v in t[1:]:
                ra, rb = (find(t[0]), find(v))
                if ra != rb:
                    parent[ra] = rb
        groups = {}
        for t in tris:
            groups.setdefault(find(t[0]), []).append(t)
        for isl in sorted(groups.values(), key=len, reverse=True):
            out.append((tex, [[uv[i] for i in t] for t in isl]))
    _ISLANDS[rel] = out
    return out

def island_mask(rel, tex, ids, w, h):
    key = (rel, tex, tuple(ids), w, h)
    if key in _MASKS:
        return _MASKS[key]
    isl = _model_islands(rel)
    m = bytearray(w * h)
    for i in ids:
        t_tex, tris = isl[i - 1]
        assert t_tex == tex, (i, t_tex, tex)
        for t in tris:
            (x0, y0), (x1, y1), (x2, y2) = [(u * w, v * h) for u, v in t]
            area = (x1 - x0) * (y2 - y0) - (x2 - x0) * (y1 - y0)
            if area == 0:
                continue
            for py in range(max(0, int(min(y0, y1, y2))), min(h - 1, int(max(y0, y1, y2))) + 1):
                cy = py + 0.5
                for px in range(max(0, int(min(x0, x1, x2))), min(w - 1, int(max(x0, x1, x2))) + 1):
                    cx = px + 0.5
                    e0 = (x1 - x0) * (cy - y0) - (cx - x0) * (y1 - y0)
                    e1 = (x2 - x1) * (cy - y1) - (cx - x1) * (y2 - y1)
                    e2 = (x0 - x2) * (cy - y2) - (cx - x2) * (y0 - y2)
                    if e0 >= 0 and e1 >= 0 and (e2 >= 0) if area > 0 else e0 <= 0 and e1 <= 0 and (e2 <= 0):
                        m[py * w + px] = 1
    _MASKS[key] = m
    return m
