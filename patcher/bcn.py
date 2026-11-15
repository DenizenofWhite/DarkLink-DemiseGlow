"""BC1/BC3/BC4 block decode/encode and BNTX block-texture helpers (own codec, no external tool)."""
import os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bntx_astc as bx
import pngio
FMT_BC1, FMT_BC4 = (26, 29)

def bc4_block_decode(b):
    r0, r1 = (b[0], b[1])
    if r0 > r1:
        pal = [r0, r1] + [((7 - i) * r0 + i * r1) // 7 for i in range(1, 7)]
    else:
        pal = [r0, r1] + [((5 - i) * r0 + i * r1) // 5 for i in range(1, 5)] + [0, 255]
    bits = int.from_bytes(b[2:8], 'little')
    return [pal[bits >> 3 * i & 7] for i in range(16)]

def bc4_block_encode(vals):
    lo, hi = (min(vals), max(vals))
    if lo == hi:
        return bytes([hi, lo]) + b'\x00' * 6
    pal = [hi, lo] + [((7 - i) * hi + i * lo) // 7 for i in range(1, 7)]
    bits = 0
    for i, v in enumerate(vals):
        k = min(range(8), key=lambda j: abs(pal[j] - v))
        bits |= k << 3 * i
    return bytes([hi, lo]) + bits.to_bytes(6, 'little')

def _565(c):
    return ((c >> 11 & 31) * 255 // 31, (c >> 5 & 63) * 255 // 63, (c & 31) * 255 // 31)

def bc1_block_decode(b):
    c0, c1 = struct.unpack_from('<HH', b, 0)
    p0, p1 = (_565(c0), _565(c1))
    if c0 > c1:
        pal = [p0, p1, tuple(((2 * a + b_) // 3 for a, b_ in zip(p0, p1))), tuple(((a + 2 * b_) // 3 for a, b_ in zip(p0, p1)))]
    else:
        pal = [p0, p1, tuple(((a + b_) // 2 for a, b_ in zip(p0, p1))), (0, 0, 0)]
    bits = struct.unpack_from('<I', b, 4)[0]
    return [pal[bits >> 2 * i & 3] for i in range(16)]

def _to565(c):
    r, g, b = c
    return min(31, (r * 31 + 127) // 255) << 11 | min(63, (g * 63 + 127) // 255) << 5 | min(31, (b * 31 + 127) // 255)

def bc1_block_encode(px):
    lum = [0.3 * r + 0.59 * g + 0.11 * b for r, g, b in px]
    hi, lo = (px[lum.index(max(lum))], px[lum.index(min(lum))])
    c0, c1 = (_to565(hi), _to565(lo))
    if c0 == c1:
        return struct.pack('<HHI', c0, c1, 0)
    if c0 < c1:
        c0, c1 = (c1, c0)
    p0, p1 = (_565(c0), _565(c1))
    pal = [p0, p1, tuple(((2 * a + b_) // 3 for a, b_ in zip(p0, p1))), tuple(((a + 2 * b_) // 3 for a, b_ in zip(p0, p1)))]
    bits = 0
    for i, c in enumerate(px):
        k = min(range(4), key=lambda j: sum(((pal[j][t] - c[t]) ** 2 for t in range(3))))
        bits |= k << 2 * i
    return struct.pack('<HHI', c0, c1, bits)

def mip_layout8(inf, bh0):
    out, off = ([], inf['data'])
    w, h = (inf['width'], inf['height'])
    for m in range(inf['mips']):
        wb, hb = (bx.div_up(w, 4), bx.div_up(h, 4))
        bh = bx.mip_bh(hb, bh0)
        out.append((off, w, h, wb, hb, bh))
        off += bx.div_up(bx.div_up(wb * 8, 64) * 64 * bx.div_up(hb, 8 * bh) * 8 * bh, 512) * 512
        w, h = (max(1, w // 2), max(1, h // 2))
    return out

def block_bh(b, inf):
    return 1 << (struct.unpack_from('<I', b, inf['brti'] + 52)[0] & 7)

def read_blocks(b, off, wb, hb, bh):
    return [[b[off + bx.gob_offset(x, y, wb, bh, 8):off + bx.gob_offset(x, y, wb, bh, 8) + 8] for x in range(wb)] for y in range(hb)]

def write_blocks(data, off, blocks, wb, hb, bh):
    for y in range(hb):
        for x in range(wb):
            a = off + bx.gob_offset(x, y, wb, bh, 8)
            data[a:a + 8] = blocks[y][x]

def decode_texture(rel, mip=0):
    b, _, _ = bx.load(rel)
    inf = bx.info(b)
    kind = inf['format'] >> 8
    off, w, h, wb, hb, bh = mip_layout8(inf, block_bh(b, inf))[mip]
    blocks = read_blocks(b, off, wb, hb, bh)
    dec = bc4_block_decode if kind == FMT_BC4 else bc1_block_decode
    px = [[None] * (wb * 4) for _ in range(hb * 4)]
    for y in range(hb):
        for x in range(wb):
            vals = dec(blocks[y][x])
            for i, v in enumerate(vals):
                px[y * 4 + i // 4][x * 4 + i % 4] = v
    return (w, h, [row[:w] for row in px[:h]])

def write_preview(path, w, h, px):
    out = bytearray(w * h * 4)
    for y in range(h):
        for x in range(w):
            v = px[y][x]
            r, g, bb = (v, v, v) if isinstance(v, int) else v
            out[(y * w + x) * 4:(y * w + x) * 4 + 4] = bytes((r, g, bb, 255))
    pngio.write_png(path, w, h, out)
if __name__ == '__main__':
    w, h, px = decode_texture(sys.argv[1], int(sys.argv[3]) if len(sys.argv) > 3 else 0)
    write_preview(sys.argv[2], w, h, px)
    print('wrote', sys.argv[2], w, h)
