"""Recolour the Master Sword's final-battle glow effect red (property records, shader float constants and a few shader instructions; every edit checks the stock value first)."""
import os, struct, sys
from compression import zstd
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bntx_astc as bx
REL = 'Effect/Weapon_Sword_Master.Nin_Ounce_NVN2.vsetb.byml.zs'
GLOW_SETS = ('Wpn_Sign_GlowVSGanonSecondHalf', 'Wpn_Sword_Slash_VSGanonSecondHalf')
RED = 0.6
WHITE = 0.12
SHADER_GROUPS = [('teal', [(1052548, 2080, 8.8), (1051972, 2050, 40.0)]), ('rgb', [(1052580, 2080, 60.0), (1052660, 2080, 55.2), (1052596, 2080, 12.0)]), ('teal', [(856820, 2080, 4.4), (856692, 2050, 20.0)]), ('rgb', [(856932, 2080, 40.0), (856948, 2080, 36.8), (856868, 2080, 8.0)]), ('teal', [(900020, 2080, 220.0), (899380, 2050, 1000.0)]), ('rgb', [(899492, 2080, 2000.0), (899988, 2080, 1840.0), (900036, 2080, 400.0)]), ('teal', [(927284, 2080, 7.5), (926500, 2050, 50.0)]), ('rgb', [(927364, 2080, 50.0), (927348, 2080, 47.5), (927380, 2080, 25.0)]), ('teal', [(874420, 2080, 1.5), (874308, 2050, 10.0)]), ('rgb', [(874724, 2080, 10.0), (874756, 2080, 9.2), (874772, 2080, 2.0)]), ('teal', [(894084, 2080, 1.5), (894148, 2050, 10.0)]), ('rgb', [(894116, 2080, 10.0), (894132, 2080, 9.2), (893012, 2080, 2.0)]), ('teal', [(948612, 2080, 1.5), (948548, 2178, 10.0)]), ('rgb', [(944964, 2080, 10.0), (944980, 2080, 9.4), (944948, 2080, 4.0)]), ('rgb', [(1009700, 2080, 0.764706), (1009716, 2080, 10.7294), (1009764, 2080, 15.0)]), ('rgb', [(1009668, 2080, 0.0078431), (1009572, 2080, 0.0627451), (1009684, 2080, 0.14902)]), ('rgb', [(1025156, 2080, 0.764706), (1025076, 2080, 10.7294), (1024980, 2080, 15.0)]), ('rgb', [(1029668, 2080, 0.764706), (1029716, 2080, 10.7294), (1029620, 2080, 15.0)])]
DEEP = (RED, 0.0, 0.03)
EMBER = (RED, 0.35, 0.03)
FLARE = (RED, WHITE, 0.08)
BLOOD = (RED, WHITE, WHITE)
GROUP_TONE = {1052548: DEEP, 1052580: EMBER, 856820: DEEP, 856932: EMBER, 900020: DEEP, 899492: EMBER, 927284: DEEP, 927364: EMBER, 874420: DEEP, 874724: EMBER, 894084: DEEP, 894116: EMBER, 948612: DEEP, 944964: EMBER, 1009700: FLARE, 1025156: FLARE, 1029668: FLARE}
PALETTE_TONES = (DEEP, EMBER)
PALETTES = {913216: 914112, 920016: 920912, 1045584: 1046480}
SPARK_GB = 0.06
SPARK_GB_VALUES = (146.4, 15.0, 131.4, 150.0, 135.0, 133.8, 10.5, 123.3)
SPARK_R_VALUES = (120.0, 6.0, 114.0, 60.0)
SPARK_BLOCKS = {988832: 989104, 1002240: 1002544}
SHADER_SET = {1024452: (2080, 0.803922, 8.0), 1024820: (2080, 0.0196078, 0.0), 1029156: (2080, 0.0627451, 0.0), 1029428: (2080, 0.14902, 0.0), 1099700: (2050, 0.84, 1.0), 1099748: (1059, -0.84, -1.0), 1099812: (2083, 0.2, 2.0)}
SWOOP_G, SWOOP_B = (0.12, 0.02)
SHADER_RAW = {1099632: ('2172120c150000000000010000e20f00', '20781215' + struct.pack('<f', SWOOP_G).hex() + '0000410000e20f00'), 1099648: ('23781515cccc4c3e0c00010000e20f00', '20781515' + struct.pack('<f', SWOOP_B).hex() + '0000410000e20f00'), 1024528: ('027a1100005d8003000f000000e41f00', '0278110000000000000f000000e41f00')}

def shader_patch(data, base, log, list_only):

    def check(off, op, old):
        at = base + off
        got_op = struct.unpack_from('<I', data, at - 4)[0] & 4095
        got = struct.unpack_from('<f', data, at)[0]
        assert got_op == op and abs(got - old) <= 0.0001 * max(1.0, abs(old)), (hex(off), hex(got_op), got, old)
        return (at, got)

    def put(off, op, old, new):
        at, got = check(off, op, old)
        log.append(f'  shader {off:#x} op {op:#x}: {got:.4g} -> {new:.4g}')
        if not list_only:
            struct.pack_into('<f', data, at, new)
    n = 0
    for kind, items in SHADER_GROUPS:
        vals = [v for _, _, v in items]
        tr, tg, tb = GROUP_TONE.get(items[0][0], BLOOD)
        if kind == 'teal':
            (ro, rop, rv), (go, gop, gv) = items
            put(ro, rop, rv, gv * tr)
            put(go, gop, gv, rv * tb)
        else:
            mx, mn = (max(vals), min(vals))
            for i, (off, op, v) in enumerate(items):
                put(off, op, v, (mx * tr, mn * tg, mn * tb)[i])
        n += len(items)
    for off, (op, old, new) in sorted(SHADER_SET.items()):
        put(off, op, old, new)
        n += 1
    for off, (old, new) in sorted(SHADER_RAW.items()):
        at = base + off
        got = bytes(data[at:at + 16])
        assert got == bytes.fromhex(old), (hex(off), got.hex())
        log.append(f'  shader {off:#x}: instruction {old} -> {new}')
        if not list_only:
            data[at:at + 16] = bytes.fromhex(new)
        n += 1
    for s, e in PALETTES.items():
        keys = []
        for p in range(base + s, base + e - 32, 16):
            trip = [struct.unpack_from('<I', data, p + 16 * k)[0] for k in range(3)]
            if all((t & 4095 == 2050 and t >> 16 & 255 == 24 + k for k, t in enumerate(trip))):
                keys.append(p - base + 4)
        assert len(keys) == 9, (hex(s), len(keys))
        for j, k in enumerate(keys):
            vals = [struct.unpack_from('<f', data, base + k + 16 * i)[0] for i in range(3)]
            mx, mn = (max(vals), min(vals))
            tone = PALETTE_TONES[j % len(PALETTE_TONES)]
            for i in range(3):
                put(k + 16 * i, 2050, vals[i], (mx if i == 0 else mn) * tone[i])
            n += 3
    for s, e in SPARK_BLOCKS.items():
        gb = 0
        for p in range(base + s, base + e, 16):
            op = struct.unpack_from('<I', data, p)[0] & 4095
            if op not in (2050, 1059, 2080):
                continue
            f = struct.unpack_from('<f', data, p + 4)[0]
            if any((abs(f - v) < 0.01 for v in SPARK_GB_VALUES)):
                put(p - base + 4, op, f, f * SPARK_GB)
                gb += 1
            else:
                assert not 1.0 < f < 500 or any((abs(f - v) < 0.01 for v in SPARK_R_VALUES)), (hex(p - base), f)
        assert gb == 10, (hex(s), gb)
        n += gb
    return n

def recolour(v):
    r, g, b = v
    if min(v) < 0:
        return None
    m, n = (max(v), min(v))
    if m <= 0 or (m - n) / m <= 0.15:
        return None
    if r == m and g <= r * 0.5 and (b <= r * 0.5):
        return None
    return (m, n * WHITE, n * WHITE)

def emitters(d, base):

    def u32(o):
        return struct.unpack_from('<I', d, base + o)[0]

    def u64(o):
        return struct.unpack_from('<Q', d, base + o)[0]

    def cstr(o):
        return d[base + o:d.index(b'\x00', base + o)].decode('ascii', 'replace')
    assert d[base + 4368:base + 4372] == b'VFX3', d[base + 4368:base + 4372]
    out = []
    o = 4368
    while True:
        if o == 4368:
            nm, ep, en = (u64(4376), u64(4384), u32(4392))
        else:
            if o + 104 > u64(4384) or u32(o) != 128 or u32(o + 4) != 20:
                break
            nm, ep, en = (u64(o + 16), u64(o + 24), u32(o + 32))
        for i in range(en):
            e = u64(ep + 8 * i)
            out.append((e, cstr(u64(e)), cstr(nm)))
        o = 4464 if o == 4368 else o + 104
    out.sort()
    return [(e, min(out[i + 1][0], e + 16384) if i + 1 < len(out) else e + 16384, en, es) for i, (e, en, es) in enumerate(out)]

def edit(d, list_only=False):
    data = bytearray(d)
    base = d.index(b'BFFH')
    n_sets, n_vals, log = (set(), 0, [])

    def put(at, v, where):
        nonlocal n_vals
        old = struct.unpack_from('<3f', data, at)
        new = recolour(old)
        if new:
            log.append(f'  {where}: ({old[0]:.4g},{old[1]:.4g},{old[2]:.4g}) -> ({new[0]:.4g},{new[1]:.4g},{new[2]:.4g})')
            if not list_only:
                struct.pack_into('<3f', data, at, *new)
            n_vals += 1
    for e, end, en, es in emitters(d, base):
        if not es.startswith(GLOW_SETS):
            continue
        n_sets.add(es)
        for p in range(e, end - 16, 8):
            info, typ = struct.unpack_from('<II', d, base + p + 8)
            if info & 255 != 9:
                continue
            if typ == 3085:
                put(base + p + 16, None, f'{es}/{en} {p:#x}')
            elif typ == 43089:
                kp, n, st = struct.unpack_from('<QII', d, base + p + 24)
                if st != 16 or not 0 < n < 64 or (not e <= kp < end):
                    continue
                put(base + p + 40, None, f'{es}/{en} {p:#x} default')
                for k in range(n):
                    put(base + kp + 16 * k, None, f'{es}/{en} {p:#x} key{k}')
    n_vals += shader_patch(data, base, log, list_only)
    return (bytes(data), n_sets, n_vals, log)

def main():
    b, dname, dicts = bx.load(REL)
    new, sets, n, log = edit(b, '--list' in sys.argv)
    print('\n'.join(log))
    print(f'{len(sets)} glow effect sets, {n} colour values -> red')
    if '--list' in sys.argv:
        return
    assert len(new) == len(b)
    out = os.path.join(HERE, 'assets', *REL.split('/'))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    packed = zstd.compress(new, level=19, zstd_dict=dicts[dname]) if dname else zstd.compress(new, 19)
    open(out, 'wb').write(packed)
    print(f'wrote {out} ({len(packed)} B, dictionary {dname})')
if __name__ == '__main__':
    main()
