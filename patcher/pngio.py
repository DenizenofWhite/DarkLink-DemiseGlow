"""Minimal PNG read/write (RGBA8) with zlib only."""
import struct, zlib

def read_png(path):
    b = open(path, 'rb').read()
    assert b[:8] == b'\x89PNG\r\n\x1a\n'
    pos, idat, w = (8, bytearray(), None)
    while pos < len(b):
        n, typ = struct.unpack_from('>I4s', b, pos)
        body = b[pos + 8:pos + 8 + n]
        if typ == b'IHDR':
            w, h, depth, ctype, _, _, inter = struct.unpack('>IIBBBBB', body)
            assert depth == 8 and ctype in (2, 6) and (inter == 0), (depth, ctype, inter)
        elif typ == b'IDAT':
            idat += body
        elif typ == b'IEND':
            break
        pos += 12 + n
    ch = 4 if ctype == 6 else 3
    raw = zlib.decompress(bytes(idat))
    stride = w * ch
    out = bytearray(w * h * 4)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        f = raw[p]
        line = bytearray(raw[p + 1:p + 1 + stride])
        p += 1 + stride
        for i in range(stride):
            a = line[i - ch] if i >= ch else 0
            up = prev[i]
            c = prev[i - ch] if i >= ch else 0
            if f == 1:
                line[i] = line[i] + a & 255
            elif f == 2:
                line[i] = line[i] + up & 255
            elif f == 3:
                line[i] = line[i] + (a + up >> 1) & 255
            elif f == 4:
                pa, pb, pc = (abs(up - c), abs(a - c), abs(a + up - 2 * c))
                pr = a if pa <= pb and pa <= pc else up if pb <= pc else c
                line[i] = line[i] + pr & 255
        prev = line
        for x in range(w):
            o = (y * w + x) * 4
            out[o:o + 3] = line[x * ch:x * ch + 3]
            out[o + 3] = line[x * ch + 3] if ch == 4 else 255
    return (w, h, out)

def write_png(path, w, h, rgba):
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += rgba[y * w * 4:(y + 1) * w * 4]

    def chunk(t, d):
        return struct.pack('>I', len(d)) + t + d + struct.pack('>I', zlib.crc32(t + d) & 4294967295)
    data = b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
    data += chunk(b'IDAT', zlib.compress(bytes(raw), 6)) + chunk(b'IEND', b'')
    open(path, 'wb').write(data)
