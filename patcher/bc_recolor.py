"""Recolour BC textures block by block: sheath roughness (glossy leather), undercoat weave and feather near-black. Only changed blocks are re-encoded; sizes stay the same."""
import os, sys
from compression import zstd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bntx_astc as bx
import bcn
GLOSSY = 55
METAL_BELOW = 96

def blocks_to_px(blocks, dec):
    return [[dec(bk) for bk in row] for row in blocks]

def process(rel, fn, mask_rel=None):
    b, dname, dicts = bx.load(rel)
    inf = bx.info(b)
    kind = inf['format'] >> 8
    dec = bcn.bc4_block_decode if kind == bcn.FMT_BC4 else bcn.bc1_block_decode
    enc = bcn.bc4_block_encode if kind == bcn.FMT_BC4 else bcn.bc1_block_encode
    data = bytearray(b)
    mlay = None
    if mask_rel:
        mb, _, _ = bx.load(mask_rel)
        minf = bx.info(mb)
        mlay = bcn.mip_layout8(minf, bcn.block_bh(mb, minf))
    changed = total = 0
    for m, (off, w, h, wb, hb, bh) in enumerate(bcn.mip_layout8(inf, bcn.block_bh(b, inf))):
        blocks = bcn.read_blocks(b, off, wb, hb, bh)
        mask = None
        if mlay:
            moff, _, _, mwb, mhb, mbh = mlay[m]
            assert (mwb, mhb) == (wb, hb)
            mask = bcn.read_blocks(mb, moff, mwb, mhb, mbh)
        for y in range(hb):
            for x in range(wb):
                total += 1
                vals = dec(blocks[y][x])
                mvals = bcn.bc4_block_decode(mask[y][x]) if mask else None
                new = [fn(v, mvals[i] if mvals else None) for i, v in enumerate(vals)]
                if new != vals:
                    blocks[y][x] = enc(new)
                    changed += 1
        bcn.write_blocks(data, off, blocks, wb, hb, bh)
    assert len(data) == len(b)
    out = os.path.join(HERE, 'assets', *rel.split('/'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    packed = zstd.compress(bytes(data), level=19, zstd_dict=dicts[dname]) if dname else zstd.compress(bytes(data), 19)
    open(out, 'wb').write(packed)
    print(f'{rel}: {changed} of {total} blocks re-encoded -> {out}')

def process_bc3(rel, fn, out_rel=None):
    b, dname, dicts = bx.load(rel)
    if out_rel:
        old, new = (os.path.basename(p).split('.')[0].encode() for p in (rel, out_rel))
        assert len(old) == len(new) and b.count(old) >= 1, (old, new, b.count(old))
        b = b.replace(old, new)
    inf = dict(bx.info(b), block=(4, 4))
    assert inf['format'] >> 8 == 28, hex(inf['format'])
    data = bytearray(b)
    bh0 = bcn.block_bh(b, inf)
    changed = total = 0
    for off, w, h, wb, hb, bh in bx.mip_layout(inf, bh0):
        blocks = bytearray(bx.deswizzle(b, off, wb, hb, bh))
        for i in range(0, len(blocks), 16):
            total += 1
            col = bcn.bc1_block_decode(bytes(blocks[i + 8:i + 16]))
            new = [fn(c, None) for c in col]
            if new != col:
                blocks[i + 8:i + 16] = bcn.bc1_block_encode(new)
                changed += 1
        bx.swizzle_into(data, off, bytes(blocks), wb, hb, bh)
    assert len(data) == len(b)
    rel = out_rel or rel
    out = os.path.join(HERE, 'assets', *rel.split('/'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    packed = zstd.compress(bytes(data), level=19, zstd_dict=dicts[dname]) if dname else zstd.compress(bytes(data), 19)
    open(out, 'wb').write(packed)
    print(f'{rel}: {changed} of {total} blocks re-encoded -> {out}')

def rough(v, metal):
    return GLOSSY if metal is not None and metal < METAL_BELOW else v

def darken(c, _):
    r, g, b = c
    k = 0.05 + 0.24 * (0.3 * r + 0.59 * g + 0.11 * b) / 255
    return (int(255 * k), int(255 * k), min(255, int(255 * k * 1.08)))
if __name__ == '__main__':
    what = sys.argv[1:] or ['sheath', 'acs', 'tile']
    if 'sheath' in what:
        process('Tex/Mt_Weapon_Sheath_Master_Rgh.bntx.zs', rough, 'Tex/Mt_Weapon_Sheath_Master_Mtl.bntx.zs')
    if 'acs' in what:
        process('Tex/Mt_Angin_Acs_Player_Adult_Alb.bntx.zs', darken)
    if 'tile' in what:
        process_bc3('Tex/Angin_Tile_A_Alb.bntx.zs', darken, 'Tex/Angin_Tile_D_Alb.bntx.zs')
    if 'feather' in what:
        process('Tex/Mt_Feather_Player_Adult_Alb.bntx.zs', darken)
