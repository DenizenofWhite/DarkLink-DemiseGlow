"""BNTX texture container: header info, Tegra block-linear (de)swizzling, mip layout, ASTC export."""
import os, struct, sys
from compression import zstd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import game as cm
ASTC_MAGIC = 1554098963

def load(rel):
    raw = zstd.decompress(open(os.path.join(cm.ROMFS, 'Pack', 'ZsDic.pack.zs'), 'rb').read())
    dicts = {nm: zstd.ZstdDict(raw[s:t]) for nm, (s, t) in cm.sarc_entries(raw).items()}
    path = rel if os.path.isabs(rel) else os.path.join(cm.ROMFS, *rel.replace('\\', '/').split('/'))
    src = open(path, 'rb').read()
    for nm, d in [(None, None)] + list(dicts.items()):
        try:
            return (zstd.decompress(src, zstd_dict=d) if d else zstd.decompress(src), nm, dicts)
        except Exception:
            continue
    raise ValueError(rel)
ASTC_BLOCKS = {45: (4, 4), 46: (5, 4), 47: (5, 5), 48: (6, 5), 49: (6, 6), 50: (8, 5), 51: (8, 6), 52: (8, 8), 53: (10, 5), 54: (10, 6), 55: (10, 8), 56: (10, 10), 57: (12, 10), 58: (12, 12)}

def info(b):
    i = b.find(b'BRTI')
    mips = struct.unpack_from('<H', b, i + 22)[0]
    fmt = struct.unpack_from('<I', b, i + 28)[0]
    w, h = struct.unpack_from('<II', b, i + 36)
    d = b.find(b'BRTD')
    data = d + 16
    bx, by = ASTC_BLOCKS.get(fmt >> 8, (0, 0))
    return {'brti': i, 'mips': mips, 'format': fmt, 'width': w, 'height': h, 'data': data, 'end': len(b), 'block': (bx, by), 'srgb': fmt & 255 == 6}

def div_up(a, b):
    return (a + b - 1) // b

def gob_offset(x, y, width_blocks, bh, bpp=16):
    gobs_wide = div_up(width_blocks * bpp, 64)
    xb = x * bpp
    gob = y // (8 * bh) * 512 * bh * gobs_wide + xb // 64 * 512 * bh + y % (8 * bh) // 8 * 512
    return gob + gob_byte(xb % 64, y % 8)

def gob_byte(xb, y):
    return xb & 15 | (y & 1) << 4 | (y >> 1 & 1) << 5 | (xb >> 4 & 1) << 6 | (y >> 2 & 1) << 7 | (xb >> 5 & 1) << 8

def surface_size(wb, hb, bh, bpp=16):
    return div_up(wb * bpp, 64) * 64 * div_up(hb, 8 * bh) * 8 * bh

def mip_bh(hb, bh):
    while bh > 1 and hb <= bh // 2 * 8:
        bh //= 2
    return bh

def deswizzle(src, off, wb, hb, bh):
    out = bytearray(wb * hb * 16)
    for y in range(hb):
        for x in range(wb):
            a = off + gob_offset(x, y, wb, bh)
            out[(y * wb + x) * 16:(y * wb + x + 1) * 16] = src[a:a + 16]
    return bytes(out)

def swizzle_into(dst, off, blocks, wb, hb, bh):
    for y in range(hb):
        for x in range(wb):
            a = off + gob_offset(x, y, wb, bh)
            dst[a:a + 16] = blocks[(y * wb + x) * 16:(y * wb + x + 1) * 16]

def astc_header(w, h, bx=8, by=8):
    return struct.pack('<I3B', ASTC_MAGIC, bx, by, 1) + w.to_bytes(3, 'little') + h.to_bytes(3, 'little') + 1 .to_bytes(3, 'little')

def mip_layout(inf, bh0):
    out, off = ([], inf['data'])
    w, h = (inf['width'], inf['height'])
    bx, by = inf['block']
    for m in range(inf['mips']):
        wb, hb = (div_up(w, bx), div_up(h, by))
        bh = mip_bh(hb, bh0)
        out.append((off, w, h, wb, hb, bh))
        off += div_up(surface_size(wb, hb, bh), 512) * 512
        w, h = (max(1, w // 2), max(1, h // 2))
    return out
if __name__ == '__main__':
    cmd, rel = (sys.argv[1], sys.argv[2])
    b, dname, dicts = load(rel)
    inf = info(b)
    if cmd == 'info':
        print(inf, 'dict', dname)
        for bh in (1, 2, 4, 8, 16):
            lay = mip_layout(inf, bh)
            end = lay[-1][0] + surface_size(lay[-1][3], lay[-1][4], lay[-1][5])
            print(f'bh {bh:2d}: mips end at {end:#x} (file {len(b):#x})')
    elif cmd == 'export':
        out = sys.argv[3]
        os.makedirs(out, exist_ok=True)
        bhs = [int(x) for x in (sys.argv[4] if len(sys.argv) > 4 else '1,2,4,8,16').split(',')]
        name = os.path.basename(rel).split('.')[0]
        for bh in bhs:
            off, w, h, wb, hb, mbh = mip_layout(inf, bh)[0]
            blocks = deswizzle(b, off, wb, hb, mbh)
            open(os.path.join(out, f'{name}_mip0_bh{bh}.astc'), 'wb').write(astc_header(w, h, *inf['block']) + blocks)
        print('exported', bhs)
    elif cmd == 'import':
        src_dir, bh0, out = (sys.argv[3], int(sys.argv[4]), sys.argv[5])
        data = bytearray(b)
        for m, (off, w, h, wb, hb, bh) in enumerate(mip_layout(inf, bh0)):
            p = os.path.join(src_dir, f'mip{m}.astc')
            a = open(p, 'rb').read()
            assert struct.unpack_from('<I', a, 0)[0] == ASTC_MAGIC
            aw, ah = (int.from_bytes(a[7:10], 'little'), int.from_bytes(a[10:13], 'little'))
            assert (aw, ah) == (w, h) and len(a) - 16 == wb * hb * 16, (m, aw, ah, w, h)
            swizzle_into(data, off, a[16:], wb, hb, bh)
        assert len(data) == len(b)
        packed = zstd.compress(bytes(data), level=19, zstd_dict=dicts[dname]) if dname else zstd.compress(bytes(data), 19)
        open(out, 'wb').write(packed)
        print('wrote', out, len(packed))
