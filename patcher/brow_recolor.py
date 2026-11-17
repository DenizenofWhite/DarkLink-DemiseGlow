"""Gear face option Black Hair and Brows: the separate eyebrow strands hidden (the brows are painted black on the face texture instead)."""
import os, struct, sys
from compression import zstd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bntx_astc as bx
import bcn
TEX = 'Eyebrow_CmnTex_Chara_Alb'

def dark(c565):
    r, g, b = bcn._565(c565)
    lum = (0.3 * r + 0.59 * g + 0.11 * b) / 255
    k = 0.004 + 0.012 * lum
    return bcn._to565((int(255 * k * 0.92), int(255 * k), int(255 * k * 1.25)))

def block(b):
    c0, c1, bits = struct.unpack('<HHI', b)
    four = c0 > c1
    n0, n1 = (dark(c0), dark(c1))
    idx = [bits >> 2 * i & 3 for i in range(16)]
    if four:
        if n0 == n1:
            if n1 > 0:
                n1 -= 1
            else:
                n0 += 1
        elif n0 < n1:
            n0, n1 = (n1, n0)
            idx = [{0: 1, 1: 0, 2: 3, 3: 2}[k] for k in idx]
    elif n0 > n1:
        n0, n1 = (n1, n0)
        idx = [{0: 1, 1: 0, 2: 2, 3: 3}[k] for k in idx]
    bits = 0
    for i, k in enumerate(idx):
        bits |= k << 2 * i
    return struct.pack('<HHI', n0, n1, bits)
HIDE = True
CLEAR = struct.pack('<HHI', 0, 0, 4294967295)

def main():
    if HIDE:
        b, dname, dicts = bx.load(f'Tex/{TEX}.bntx.zs')
        inf = bx.info(b)
        data = bytearray(b)
        for m, (off, w, h, wb, hb, bh) in enumerate(bcn.mip_layout8(inf, bcn.block_bh(b, inf))):
            bcn.write_blocks(data, off, [[CLEAR] * wb for _ in range(hb)], wb, hb, bh)
        assert len(data) == len(b)
        out = os.path.join(HERE, 'assets', 'Tex', TEX + '.bntx.zs')
        open(out, 'wb').write(zstd.compress(bytes(data), level=19, zstd_dict=dicts[dname]) if dname else zstd.compress(bytes(data), 19))
        print(f'wrote assets/Tex/{TEX}.bntx.zs: fully transparent (brow strands hidden)')
        return
    b, dname, dicts = bx.load(f'Tex/{TEX}.bntx.zs')
    inf = bx.info(b)
    assert inf['format'] >> 8 == bcn.FMT_BC1, hex(inf['format'])
    data = bytearray(b)
    for m, (off, w, h, wb, hb, bh) in enumerate(bcn.mip_layout8(inf, bcn.block_bh(b, inf))):
        blocks = bcn.read_blocks(b, off, wb, hb, bh)
        new = [[block(blk) for blk in row] for row in blocks]
        for row, nrow in zip(blocks, new):
            for o, n in zip(row, nrow):
                ta = [c == (0, 0, 0) and struct.unpack_from('<H', o)[0] <= struct.unpack_from('<H', o, 2)[0] and (struct.unpack_from('<I', o, 4)[0] >> 2 * i & 3 == 3) for i, c in enumerate(bcn.bc1_block_decode(o))]
                tb = [struct.unpack_from('<H', n)[0] <= struct.unpack_from('<H', n, 2)[0] and struct.unpack_from('<I', n, 4)[0] >> 2 * i & 3 == 3 for i in range(16)]
                assert ta == tb
        bcn.write_blocks(data, off, new, wb, hb, bh)
        print(f'mip {m}: {w}x{h} ({wb * hb} blocks)')
    assert len(data) == len(b)
    out = os.path.join(HERE, 'assets', 'Tex', TEX + '.bntx.zs')
    packed = zstd.compress(bytes(data), level=19, zstd_dict=dicts[dname]) if dname else zstd.compress(bytes(data), 19)
    open(out, 'wb').write(packed)
    print(f'wrote assets/Tex/{TEX}.bntx.zs ({len(packed)} B)')
if __name__ == '__main__':
    main()
