"""BYML read/write and SARC archive helpers (replace a file, sliding the following files)."""
import struct

def byml_read(b):
    assert b[:2] == b'YB', b[:2]
    ver, ktab, stab, root = struct.unpack_from('<HIII', b, 2)

    def strtab(off):
        if not off:
            return []
        n = int.from_bytes(b[off + 1:off + 4], 'little')
        offs = struct.unpack_from(f'<{n + 1}I', b, off + 4)
        return [b[off + o:b.index(b'\x00', off + o)].decode('utf-8') for o in offs[:n]]
    keys, strs = (strtab(ktab), strtab(stab))

    def val(t, raw):
        if t == 160:
            return ('str', strs[raw])
        if t == 208:
            return ('bool', bool(raw))
        if t == 209:
            return ('int', struct.unpack('<i', struct.pack('<I', raw))[0])
        if t == 210:
            return ('float', struct.unpack('<f', struct.pack('<I', raw))[0])
        if t == 211:
            return ('uint', raw)
        if t == 212:
            return ('i64', struct.unpack_from('<q', b, raw)[0])
        if t == 213:
            return ('u64', struct.unpack_from('<Q', b, raw)[0])
        if t == 214:
            return ('f64', struct.unpack_from('<d', b, raw)[0])
        if t == 255:
            return ('null', None)
        if t in (192, 193):
            return node(raw)
        raise ValueError(f'BYML type {t:#x} not supported by this writer')

    def node(off):
        t, n = (b[off], int.from_bytes(b[off + 1:off + 4], 'little'))
        if t == 193:
            out = {}
            for i in range(n):
                e = off + 4 + i * 8
                out[keys[int.from_bytes(b[e:e + 3], 'little')]] = val(b[e + 3], struct.unpack_from('<I', b, e + 4)[0])
            return out
        if t == 192:
            types = b[off + 4:off + 4 + n]
            vo = off + 4 + (n + 3 & ~3)
            return [val(types[i], struct.unpack_from('<I', b, vo + i * 4)[0]) for i in range(n)]
        raise ValueError(f'BYML node {t:#x} not supported by this writer')
    return (ver, node(root) if root else None)

def _collect(tree, keys, strs):
    if isinstance(tree, dict):
        for k, v in tree.items():
            keys.add(k)
            _collect(v, keys, strs)
    elif isinstance(tree, list):
        for v in tree:
            _collect(v, keys, strs)
    elif tree[0] == 'str':
        strs.add(tree[1])

def _strtab(items):
    items = sorted(items, key=lambda s: s.encode('utf-8'))
    n = len(items)
    head = bytearray(b'\xc2' + n.to_bytes(3, 'little'))
    data, offs = (bytearray(), [])
    base = 4 + 4 * (n + 1)
    for s in items:
        offs.append(base + len(data))
        data += s.encode('utf-8') + b'\x00'
    offs.append(base + len(data))
    out = head + struct.pack(f'<{n + 1}I', *offs) + data
    out += b'\x00' * (-len(out) % 4)
    return (out, {s: i for i, s in enumerate(items)})

def byml_write(version, tree):
    keys, strs = (set(), set())
    _collect(tree, keys, strs)
    ktab, kidx = _strtab(keys)
    stab, sidx = _strtab(strs) if strs else (b'', {})
    out = bytearray(16)
    k_off = len(out)
    out += ktab
    s_off = len(out) if strs else 0
    out += stab
    pending = []

    def scalar(v):
        t, x = v
        if t == 'str':
            return (160, sidx[x])
        if t == 'bool':
            return (208, int(x))
        if t == 'int':
            return (209, struct.unpack('<I', struct.pack('<i', x))[0])
        if t == 'float':
            return (210, struct.unpack('<I', struct.pack('<f', x))[0])
        if t == 'uint':
            return (211, x)
        if t == 'null':
            return (255, 0)
        raise ValueError(f'writer: 64-bit values not supported ({t})')

    def emit(node):
        start = len(out)
        if isinstance(node, dict):
            items = sorted(node.items(), key=lambda kv: kidx[kv[0]])
            out.extend(b'\xc1' + len(items).to_bytes(3, 'little'))
            for k, v in items:
                if isinstance(v, (dict, list)):
                    out.extend(kidx[k].to_bytes(3, 'little') + bytes([193 if isinstance(v, dict) else 192]))
                    pending.append((len(out), v))
                    out.extend(b'\x00\x00\x00\x00')
                else:
                    t, raw = scalar(v)
                    out.extend(kidx[k].to_bytes(3, 'little') + bytes([t]) + struct.pack('<I', raw))
        else:
            n = len(node)
            out.extend(b'\xc0' + n.to_bytes(3, 'little'))
            types, vals = ([], [])
            for v in node:
                if isinstance(v, (dict, list)):
                    types.append(193 if isinstance(v, dict) else 192)
                    vals.append(v)
                else:
                    t, raw = scalar(v)
                    types.append(t)
                    vals.append(raw)
            out.extend(bytes(types) + b'\x00' * (-n % 4))
            for v in vals:
                if isinstance(v, (dict, list)):
                    pending.append((len(out), v))
                    out.extend(b'\x00\x00\x00\x00')
                else:
                    out.extend(struct.pack('<I', v))
        return start
    root_off = emit(tree) if tree is not None else 0
    while pending:
        pos, node = pending.pop(0)
        struct.pack_into('<I', out, pos, emit(node))
    out[0:16] = b'YB' + struct.pack('<HIII', version, k_off, s_off, root_off)
    return bytes(out)

def sarc_fits_in_place(orig, name, new_len):
    data_off = struct.unpack_from('<I', orig, 12)[0]
    n = struct.unpack_from('<H', orig, 20 + 6)[0]
    nodes_at = 20 + 12
    nodes = [struct.unpack_from('<IIII', orig, nodes_at + i * 16) for i in range(n)]
    names_at = nodes_at + n * 16 + 8
    starts = sorted((s for _, _, s, _ in nodes))
    for _, attr, s, t in nodes:
        p = names_at + (attr & 65535) * 4
        if orig[p:orig.index(b'\x00', p)].decode() == name:
            nxt = min([x for x in starts if x > s] + [len(orig) - data_off])
            return s + new_len <= nxt
    raise KeyError(name)

def sarc_shift_replace(orig, name, blob, align=8):
    assert orig[:4] == b'SARC'
    data_off = struct.unpack_from('<I', orig, 12)[0]
    n = struct.unpack_from('<H', orig, 20 + 6)[0]
    nodes_at = 20 + 12
    nodes = [list(struct.unpack_from('<IIII', orig, nodes_at + i * 16)) for i in range(n)]
    names_at = nodes_at + n * 16 + 8
    idx = None
    for i, (_, attr, s, t) in enumerate(nodes):
        p = names_at + (attr & 65535) * 4
        if orig[p:orig.index(b'\x00', p)].decode() == name:
            idx = i
    assert idx is not None, name
    s0, t0 = (nodes[idx][2], nodes[idx][3])
    grow = len(blob) - (t0 - s0)
    delta = max(0, (grow + align - 1) // align * align)
    nxt = min([nd[2] for nd in nodes if nd[2] > s0] + [len(orig) - data_off])
    if s0 + len(blob) <= nxt:
        delta = 0
    out = bytearray(orig[:data_off + s0]) + blob
    out += b'\x00' * (data_off + nxt + delta - len(out))
    out += orig[data_off + nxt:]
    nodes[idx][3] = s0 + len(blob)
    for nd in nodes:
        if nd[2] >= nxt and nd is not nodes[idx]:
            nd[2] += delta
            nd[3] += delta
    for i, nd in enumerate(nodes):
        struct.pack_into('<II', out, nodes_at + i * 16 + 8, nd[2], nd[3])
    struct.pack_into('<I', out, 8, len(out))
    return bytes(out)

def sarc_rebuild(orig, replace, align=8):
    assert orig[:4] == b'SARC'
    data_off = struct.unpack_from('<I', orig, 12)[0]
    n = struct.unpack_from('<H', orig, 20 + 6)[0]
    nodes_at = 20 + 12
    nodes = [list(struct.unpack_from('<IIII', orig, nodes_at + i * 16)) for i in range(n)]
    names_at = nodes_at + n * 16 + 8
    names = []
    for _, attr, s, t in nodes:
        p = names_at + (attr & 65535) * 4
        names.append(orig[p:orig.index(b'\x00', p)].decode())
    starts = sorted((s for _, _, s, _ in nodes))
    data_end = len(orig) - data_off
    out = bytearray(orig)
    for i, nm in enumerate(names):
        if nm not in replace:
            continue
        blob = replace[nm]
        s, t = (nodes[i][2], nodes[i][3])
        nxt = min([x for x in starts if x > s] + [data_end])
        out[data_off + s:data_off + t] = b'\x00' * (t - s)
        if s + len(blob) <= nxt:
            out[data_off + s:data_off + s + len(blob)] = blob
            nodes[i][3] = s + len(blob)
        else:
            end = len(out) - data_off
            pos = (end + align - 1) // align * align
            out += b'\x00' * (pos - end) + blob
            nodes[i][2], nodes[i][3] = (pos, pos + len(blob))
        struct.pack_into('<II', out, nodes_at + i * 16 + 8, nodes[i][2], nodes[i][3])
    struct.pack_into('<I', out, 8, len(out))
    return bytes(out)
