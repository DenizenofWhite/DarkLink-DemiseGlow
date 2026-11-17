"""Give Link's models their own renamed copies of the recoloured textures (same-length names), so nothing else in the game that shares the stock textures changes."""
import os, struct, sys
from compression import zstd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bntx_astc as bx
import game as cm
CLOTHES_MAP = {f'Mt_{p}_Player_Adult_Alb': f'Mt_{p}_Player_DkLnk_Alb' for p in ('Vest', 'Inner', 'Leater_Upper', 'Boots', 'Glove', 'Angin_Acs', 'Feather')}
SHEATH_MAP = {'Mt_Weapon_Sheath_Master_Alb': 'Mt_Weapon_Sheath_DkLink_Alb'}
HEAD_MAP = {'Mt_Hairs_Player_Adult_Alb': 'Mt_Hairs_Player_DkLnk_Alb', 'Eye_Inner_Iris_CmnTex_Chara_Eye_Alb': 'Eye_Inner_Iris_CmnTex_DkLnk_Eye_Alb', 'CmnTex_Chara_Hair_LUT_A_Gn0': 'CmnTex_Chara_Hair_LUT_K_Gn0', 'Mt_Face_Player_Adult_Alb': 'Mt_Face_Player_DkLnk_Alb', 'Eyebrow_CmnTex_Chara_Alb': 'Eyebrow_CmnTex_DkLnk_Alb', 'Mt_Face_Player_Adult_Rgh': 'Mt_Face_Player_DkLnk_Rgh'}
HEAD_NEEDS = {'Mt_Hairs_Player_Adult_Alb': ('hair',), 'Eye_Inner_Iris_CmnTex_Chara_Eye_Alb': ('eyes',), 'CmnTex_Chara_Hair_LUT_A_Gn0': ('hair',), 'Mt_Face_Player_Adult_Alb': ('hair', 'liner'), 'Eyebrow_CmnTex_Chara_Alb': ('hair',), 'Mt_Face_Player_Adult_Rgh': ('liner',)}
OPTS = {'hair': True, 'eyes': True, 'liner': True}

def configure(hair=True, eyes=True, liner=True):
    global TEX_COPIES, MODELS, PARAM_COPIES
    OPTS.update(hair=hair, eyes=eyes, liner=liner)
    head = {k: v for k, v in HEAD_MAP.items() if any((OPTS[o] for o in HEAD_NEEDS[k]))}
    TEX_COPIES = {**CLOTHES_MAP, **SHEATH_MAP, **head}
    MODELS = {'Model/Player_Adult.Player_Adult.bfres.zs': {**CLOTHES_MAP, **head, 'Angin_Tile_A_Alb': 'Angin_Tile_D_Alb'}, 'Model/Player_Adult_Dark.Player_Adult_Dark.bfres.zs': dict(CLOTHES_MAP), 'Model/Weapon_Sheath_Master.Weapon_Sheath_Master.bfres.zs': dict(SHEATH_MAP)}
    PARAM_COPIES = dict(PARAM_ALL) if hair else {}

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
PARAM_ALL = {'Model/Player_Adult.Player_Adult.bfres.zs': [('Mt_Hairs', 'Model/Npc_Hylia_MU_Ingo_Adult.Npc_Hylia_MU_Ingo_Adult.bfres.zs', 'Mt_Hair')]}
configure()

def fmat_by_name(b, name):
    i = b.find(b'FMAT')
    while i >= 0:
        if rstr(b, u64(b, i + 8)) == name.encode():
            return i
        i = b.find(b'FMAT', i + 4)
    raise KeyError(name)

def param_block(b, at):
    offp, datap = (u64(b, at + 80), u64(b, at + 88))
    size = struct.unpack_from('<H', b, offp)[0]
    return (offp, datap, size)

def copy_params(rel, copies):
    out = os.path.join(HERE, 'assets', *rel.split('/'))
    raw = open(out, 'rb').read()
    _, dname, dicts = bx.load(rel)
    b = bytearray(zstd.decompress(raw, zstd_dict=dicts[dname]) if dname else zstd.decompress(raw))
    for mat, src_rel, src_mat in copies:
        s = bx.load(src_rel)[0]
        at, sat = (fmat_by_name(b, mat), fmat_by_name(s, src_mat))
        offp, datap, size = param_block(b, at)
        soffp, sdatap, ssize = param_block(s, sat)
        assert size == ssize and b[offp:offp + 64] == s[soffp:soffp + 64], (mat, size, ssize)
        diff = sum((1 for k in range(0, size, 4) if b[datap + k:datap + k + 4] != s[sdatap + k:sdatap + k + 4]))
        b[datap:datap + size] = s[sdatap:sdatap + size]
        print(f"{rel}: {mat} values <- {src_rel.split('/')[-1].split('.')[0]} {src_mat} ({diff} floats changed)")
    open(out, 'wb').write(zstd.compress(bytes(b), level=15, zstd_dict=dicts[dname]) if dname else zstd.compress(bytes(b), 15))

def main():
    copy_textures()
    for rel, mapping in MODELS.items():
        patch_model(rel, mapping)
    for rel, copies in PARAM_COPIES.items():
        copy_params(rel, copies)
if __name__ == '__main__':
    main()
