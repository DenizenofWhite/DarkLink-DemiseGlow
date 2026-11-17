"""Gear face option Black Hair and Brows: Link's hair texture (BC7) recoloured near-black, glossy."""
import os, struct, sys
from compression import zstd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bntx_astc as bx
import bc7
TEX = 'Mt_Hairs_Player_Adult_Alb'
_ALPHA = [int(round(255 * (a / 255) ** 0.6)) for a in range(256)]

def recolor_px(p):
    r, g, b, a = p
    lum = (0.3 * r + 0.59 * g + 0.11 * b) / 255
    k = 0.01 + 0.055 * lum
    return (min(255, int(255 * k * 0.92)), min(255, int(255 * k)), min(255, int(255 * k * 1.25)), _ALPHA[a])

def main():
    b, dname, dicts = bx.load(f'Tex/{TEX}.bntx.zs')
    inf = bx.info(b)
    assert inf['format'] == 8198, hex(inf['format'])
    inf['block'] = (4, 4)
    bh0 = 1 << (struct.unpack_from('<I', b, inf['brti'] + 52)[0] & 7)
    data = bytearray(b)
    cache = {}
    for m, (off, w, h, wb, hb, bh) in enumerate(bx.mip_layout(inf, bh0)):
        raw = bx.deswizzle(b, off, wb, hb, bh)
        out = bytearray(len(raw))
        for i in range(0, len(raw), 16):
            blk = raw[i:i + 16]
            enc = cache.get(blk)
            if enc is None:
                enc = cache[blk] = bc7.encode_mode6([recolor_px(p) for p in bc7.decode_block(blk)])
            out[i:i + 16] = enc
        bx.swizzle_into(data, off, bytes(out), wb, hb, bh)
        print(f'hair mip {m}: {w}x{h} ({wb * hb} blocks)')
    assert len(data) == len(b)
    os.makedirs(os.path.join(HERE, 'assets', 'Tex'), exist_ok=True)
    dst = os.path.join(HERE, 'assets', 'Tex', TEX + '.bntx.zs')
    packed = zstd.compress(bytes(data), level=19, zstd_dict=dicts[dname]) if dname else zstd.compress(bytes(data), 19)
    open(dst, 'wb').write(packed)
    print(f'wrote assets/Tex/{TEX}.bntx.zs ({len(packed)} B)')
if __name__ == '__main__':
    main()
