"""Gear face option Eyeliner: glossier eyelid edges (face roughness texture, BC4)."""
import os, sys
from compression import zstd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bntx_astc as bx
import bcn
from recolor_gear import FACE_EYES, LINER_R, LINER_FADE, LINER_LOWER_ONLY, lid_liner
TEX = 'Mt_Face_Player_Adult_Rgh'
GLOSS = 30

def weight(u, v):
    best = 0.0
    for cx, cy in FACE_EYES:
        rr = ((u - cx) ** 2 + (v - cy) ** 2) ** 0.5
        ring = 1.0 if rr <= LINER_R else max(0.0, 1 - (rr - LINER_R) / LINER_FADE)
        if LINER_LOWER_ONLY:
            ring *= max(0.0, min(1.0, (v - cy + 0.004) / 0.008))
        best = max(best, ring)
    return best

def main():
    b, dname, dicts = bx.load(f'Tex/{TEX}.bntx.zs')
    inf = bx.info(b)
    assert inf['format'] >> 8 == bcn.FMT_BC4, hex(inf['format'])
    data = bytearray(b)
    for m, (off, w, h, wb, hb, bh) in enumerate(bcn.mip_layout8(inf, bcn.block_bh(b, inf))):
        blocks = bcn.read_blocks(b, off, wb, hb, bh)
        changed = 0
        for by in range(hb):
            for bxk in range(wb):
                ws = [max(weight((bxk * 4 + i % 4 + 0.5) / w, (by * 4 + i // 4 + 0.5) / h), lid_liner(bxk * 4 + i % 4, by * 4 + i // 4, w, h) if bxk * 4 + i % 4 < w and by * 4 + i // 4 < h else 0.0) for i in range(16)]
                if max(ws) == 0:
                    continue
                vals = bcn.bc4_block_decode(blocks[by][bxk])
                new = [int(round(v * (1 - a) + min(v, GLOSS) * a)) for v, a in zip(vals, ws)]
                if new != vals:
                    blocks[by][bxk] = bcn.bc4_block_encode(new)
                    changed += 1
        bcn.write_blocks(data, off, blocks, wb, hb, bh)
        print(f'mip {m}: {w}x{h}, {changed} blocks glossed')
    assert len(data) == len(b)
    out = os.path.join(HERE, 'assets', 'Tex', TEX + '.bntx.zs')
    packed = zstd.compress(bytes(data), level=19, zstd_dict=dicts[dname]) if dname else zstd.compress(bytes(data), 19)
    open(out, 'wb').write(packed)
    print(f'wrote assets/Tex/{TEX}.bntx.zs ({len(packed)} B)')
if __name__ == '__main__':
    main()
