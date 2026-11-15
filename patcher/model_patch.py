"""Give Link's models their own renamed copies of the recoloured textures (same-length names), so nothing else in the game that shares the stock textures changes."""
import os, struct, sys
from compression import zstd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bntx_astc as bx
import game as cm
CLOTHES_MAP = {f'Mt_{p}_Player_Adult_Alb': f'Mt_{p}_Player_DkLnk_Alb' for p in ('Vest', 'Inner', 'Leater_Upper', 'Boots', 'Glove', 'Angin_Acs', 'Feather')}
SHEATH_MAP = {'Mt_Weapon_Sheath_Master_Alb': 'Mt_Weapon_Sheath_DkLink_Alb'}
TEX_COPIES = {**CLOTHES_MAP, **SHEATH_MAP}
MODELS = {'Model/Player_Adult.Player_Adult.bfres.zs': {**CLOTHES_MAP, 'Angin_Tile_A_Alb': 'Angin_Tile_D_Alb'}, 'Model/Player_Adult_Dark.Player_Adult_Dark.bfres.zs': dict(CLOTHES_MAP), 'Model/Weapon_Sheath_Master.Weapon_Sheath_Master.bfres.zs': dict(SHEATH_MAP)}

def u64(b, o):
    return struct.unpack_from('<Q', b, o)[0]

def rstr(b, o):
    n = struct.unpack_from('<H', b, o)[0]
    return b[o + 2:o + 2 + n]

def copy_textures():
    for old, new in TEX_COPIES.items():
        assert len(old) == len(new) and old[-4:] == new[-4:], (old, new)
        assert not os.path.exists(os.path.join(cm.ROMFS, 'Tex', new + '.bntx.zs')), new
        _, dname, dicts = bx.load(f'Tex/{old}.bntx.zs')
        src = os.path.join(HERE, 'assets', 'Tex', old + '.bntx.zs')
        raw = open(src, 'rb').read()
        b = zstd.decompress(raw, zstd_dict=dicts[dname]) if dname else zstd.decompress(raw)
        n = b.count(old.encode())
        assert n >= 1, (old, n)
        b = b.replace(old.encode(), new.encode())
        out = os.path.join(HERE, 'assets', 'Tex', new + '.bntx.zs')
        open(out, 'wb').write(zstd.compress(b, level=19, zstd_dict=dicts[dname]) if dname else zstd.compress(b, 19))
        print(f'Tex/{new}: copy of the recoloured {old} ({n} name occurrence(s) replaced)')

def patch_model(rel, mapping):
    b, dname, dicts = bx.load(rel)
    data = bytearray(b)
    arrays = []
    i = b.find(b'FMAT')
    while i >= 0:
        arrays.append(u64(b, i + 32))
        i = b.find(b'FMAT', i + 4)
    st = b.find(b'_STR')
    cnt = struct.unpack_from('<I', b, st + 16)[0]
    p = st + 24
    for _ in range(cnt + 1):
        n = struct.unpack_from('<H', b, p)[0]
        p += 2 + n + 1
        p += p & 1
    log = []
    for old, new in mapping.items():
        enc = struct.pack('<H', len(old)) + old.encode() + b'\x00'
        locs = [j for j in range(st, len(b) - len(enc)) if b[j:j + len(enc)] == enc]
        assert len(locs) == 1, (rel, old, locs)
        ptrs = [q for q in range(0, len(b) - 8, 8) if u64(b, q) == locs[0]]
        assert ptrs and all((any((0 <= q - a < 8 * 16 for a in arrays)) for q in ptrs)), (rel, old, ptrs)
        p += (8 - p % 8) % 8
        blob = struct.pack('<H', len(new)) + new.encode() + b'\x00'
        assert all((c == 0 for c in b[p:p + len(blob) + 8])), (rel, 'padding not free at', hex(p))
        data[p:p + len(blob)] = blob
        for q in ptrs:
            struct.pack_into('<Q', data, q, p)
        log.append(f'{old} -> {new} ({len(ptrs)} slot(s))')
        p += len(blob)
    assert len(data) == len(b)
    out = os.path.join(HERE, 'assets', *rel.split('/'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    packed = zstd.compress(bytes(data), level=15, zstd_dict=dicts[dname]) if dname else zstd.compress(bytes(data), 15)
    open(out, 'wb').write(packed)
    print(f'{rel}: ' + '; '.join(log))

def main():
    copy_textures()
    for rel, mapping in MODELS.items():
        patch_model(rel, mapping)
if __name__ == '__main__':
    main()
