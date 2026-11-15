"""Read the game's resource size table (RESTBL)."""
import os, struct, sys, zlib
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compression import zstd
import game as cm
RSTB_REL = 'System/Resource/ResourceSizeTable.Product.111.Nin_Ounce_NVN2.rsizetable.zs'

def load_rstb(path):
    b = zstd.decompress(open(path, 'rb').read())
    assert b[:6] == b'RESTBL', b[:8]
    ver, slen, ncrc, nname = struct.unpack_from('<IIII', b, 6)
    off = 22
    crc = {}
    for i in range(ncrc):
        h, s = struct.unpack_from('<II', b, off + i * 8)
        crc[h] = s
    off += ncrc * 8
    names = {}
    for i in range(nname):
        nm = b[off:off + slen].split(b'\x00')[0].decode()
        names[nm] = struct.unpack_from('<I', b, off + slen)[0]
        off += slen + 4
    return {'version': ver, 'slen': slen, 'crc': crc, 'names': names}

def lookup(t, key):
    if key in t['names']:
        return t['names'][key]
    return t['crc'].get(zlib.crc32(key.encode()))
if __name__ == '__main__':
    raw = zstd.decompress(open(os.path.join(cm.ROMFS, 'Pack', 'ZsDic.pack.zs'), 'rb').read())
    dicts = [zstd.ZstdDict(raw[s:t]) for nm, (s, t) in cm.sarc_entries(raw).items()]
    van = load_rstb(os.path.join(cm.ROMFS, *RSTB_REL.split('/')))
    print(f"vanilla RESTBL v{van['version']}: {len(van['crc'])} crc entries, {len(van['names'])} named")
    for rel in sys.argv[1:]:
        src = open(os.path.join(cm.ROMFS, *rel.split('/')), 'rb').read()
        size = None
        for d in [None] + dicts:
            try:
                size = len(zstd.decompress(src, zstd_dict=d) if d else zstd.decompress(src))
                break
            except Exception:
                continue
        key = rel[:-3] if rel.endswith('.zs') else rel
        print(f'{key}: file {size}, table {lookup(van, key)}')
