"""Recolour the ASTC textures (sheath, clothes, Dark sword jewel, menu icons): export mips for astcenc to decode, recolour by hue/metal map, astcenc encodes, splice only the changed blocks."""
import colorsys, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bntx_astc as bx
import pngio
ASSETS = os.path.join(HERE, 'assets')
SETS = {'weapons': ['Mt_Weapon_Sword_Master_Alb', 'Mt_Weapon_Sheath_Master_Alb'], 'clothes': ['Mt_Vest_Player_Adult_Alb', 'Mt_Inner_Player_Adult_Alb', 'Mt_Leater_Upper_Player_Adult_Alb', 'Mt_Boots_Player_Adult_Alb', 'Mt_Glove_Player_Adult_Alb'], 'darksword': ['Mt_Weapon_Sword_Master_Dark_Alb'], 'clothes_metal': ['Mt_Leater_Upper_Player_Adult_Alb', 'Mt_Boots_Player_Adult_Alb', 'Mt_Glove_Player_Adult_Alb'], 'icons': ['UI/Tex/Icon/Weapon_Sword_Master', 'UI/Tex/Icon/Weapon_Shield_Hylian', 'UI/Tex/Icon/Armor_Adult_Normal']}

def use_set(s):
    global SET, TEXTURES, WORK
    SET, TEXTURES = (s, SETS[s])
    WORK = os.path.join(HERE, 'work', {'weapons': 'gear', 'clothes_metal': 'clothes'}.get(s, s))
use_set('weapons')
GEAR_WORK = os.path.join(HERE, 'work', 'gear')

def rel(t):
    return (t if '/' in t else 'Tex/' + t) + '.bntx.zs'

def base(t):
    return t.split('/')[-1]

def pick_bh(b, inf):
    return 1 << (struct.unpack_from('<I', b, inf['brti'] + 52)[0] & 7)

def interior(mask, w, h, r):
    if r <= 0:
        return set(mask)
    inner = set()
    for x, y in mask:
        if all(((x + dx, y + dy) in mask for dx in range(-r, r + 1) for dy in range(-r, r + 1))):
            inner.add((x, y))
    return inner

def jewel_colour(inner, v):
    if inner:
        return (min(255, int(150 + 105 * v)), 16, 20)
    g = min(255, int(130 + 115 * v))
    return (g, g, min(255, int(g * 1.03)))

def guard_colour(v):
    f = v / 0.72
    return (min(255, int(72 * f)), min(255, int(72 * f)), min(255, int(136 * f)))

def gem_shader(gem, px, w):
    import math
    pts = list(gem)
    cx = sum((p[0] for p in pts)) / len(pts)
    cy = sum((p[1] for p in pts)) / len(pts)
    sxx = sum(((p[0] - cx) ** 2 for p in pts))
    syy = sum(((p[1] - cy) ** 2 for p in pts))
    sxy = sum(((p[0] - cx) * (p[1] - cy) for p in pts))
    ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
    ax, ay = (math.cos(ang), math.sin(ang))
    along = [(p[0] - cx) * ax + (p[1] - cy) * ay for p in pts]
    lo, hi = (min(along), max(along))
    lum = {p: 0.3 * px[(p[1] * w + p[0]) * 4] + 0.59 * px[(p[1] * w + p[0]) * 4 + 1] + 0.11 * px[(p[1] * w + p[0]) * 4 + 2] for p in pts}
    mean = sum(lum.values()) / len(lum)
    top = min(pts, key=lambda p: (p[0] - cx) * ax + (p[1] - cy) * ay)
    flip = 1 if top[1] > cy else -1
    out = {}
    for p, a in zip(pts, along):
        t = (a - lo) / (hi - lo or 1)
        t = t if flip < 0 else 1 - t
        side = (p[0] - cx) * -ay + (p[1] - cy) * ax
        lit = 1.0 if side < 0 else 0.62
        detail = 1 + 1.6 * (lum[p] - mean) / 255
        r = (235 - 95 * t) * lit * detail
        out[p] = (max(40, min(255, int(r))), max(0, min(255, int(r * 0.07))), max(0, min(255, int(r * 0.1))))
    cand = []
    for p, a in zip(pts, along):
        side = (p[0] - cx) * -ay + (p[1] - cy) * ax
        t = (a - lo) / (hi - lo or 1)
        t = t if flip < 0 else 1 - t
        if side < 0 and 0.15 <= t <= 0.45:
            cand.append((p, side, t))
    if cand:
        mid = sorted((c[1] for c in cand))[len(cand) // 2]
        for p, _, _ in sorted(cand, key=lambda c: abs(c[1] - mid) + abs(c[2] - 0.28) * 6)[:4]:
            out[p] = (255, 200, 200)
    return out

def leather(v):
    k = 0.05 + 0.2 * v
    return (int(255 * k * 1.04), int(255 * k), int(255 * k * 0.96))

def recolor_pixel(tex, r, g, b):
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    hue = h * 360
    gold = 25 <= hue <= 60 and s > 0.3 and (v > 0.25)
    if '/Icon/' in tex:
        bluish = 200 <= hue <= 300 and s > 0.2
        reddish = (hue >= 330 or hue <= 15) and s > 0.35
        green = 60 <= hue <= 170 and s > 0.2
        if tex.endswith('Weapon_Sword_Master'):
            if bluish:
                k = 0.06 + 0.3 * v
                return (int(255 * k), int(255 * k), min(255, int(255 * k * 1.08)))
            if 60 <= hue <= 170 and s > 0.12:
                return leather(v)
            if gold:
                return (min(255, int(140 + 115 * v)), 18, 22)
            return None
        if tex.endswith('Weapon_Shield_Hylian'):
            if bluish:
                k = 0.04 + 0.2 * v
                return (int(255 * k), int(255 * k), int(255 * k))
            if reddish or gold:
                grey = min(255, int((0.3 * r + 0.59 * g + 0.11 * b) * 0.85))
                return (grey, grey, grey)
            return None
        if green or reddish or (s > 0.25 and (not gold)):
            k = 0.05 + 0.24 * (0.3 * r + 0.59 * g + 0.11 * b) / 255
            return (int(255 * k), int(255 * k), min(255, int(255 * k * 1.08)))
        if gold:
            grey = min(255, int((0.3 * r + 0.59 * g + 0.11 * b) * 1.05))
            return (grey, grey, grey)
        return None
    if 'Player_Adult' in tex:
        if gold:
            lum = 0.3 * r + 0.59 * g + 0.11 * b
            grey = min(255, int(lum * 1.05))
            return (grey, grey, min(255, int(grey * 1.03)))
        k = 0.05 + 0.24 * (0.3 * r + 0.59 * g + 0.11 * b) / 255
        return (int(255 * k), int(255 * k), min(255, int(255 * k * 1.08)))
    blue = 205 <= hue <= 265 and s > 0.22 and (v > 0.12)
    if blue:
        k = 0.1 + 0.22 * v
        return (int(255 * k), int(255 * k), int(255 * k * 1.06))
    if gold and tex == 'Mt_Weapon_Sword_Master_Alb':
        return (min(255, int(255 * (0.55 + 0.4 * v))), int(255 * 0.05 * v), int(255 * 0.07 * v))
    if gold and tex == 'Mt_Weapon_Sheath_Master_Alb':
        lum = 0.3 * r + 0.59 * g + 0.11 * b
        grey = min(255, int(lum * 1.08))
        return (grey, grey, min(255, int(grey * 1.03)))
    return None

def export():
    os.makedirs(WORK, exist_ok=True)
    jobs = []
    for t in TEXTURES:
        b, _, _ = bx.load(rel(t))
        inf = bx.info(b)
        assert inf['block'][0] and inf['srgb'], (t, inf)
        bh0 = pick_bh(b, inf)
        n = base(t)
        print(t, 'block', inf['block'], 'gob stack', bh0)
        for m, (off, w, h, wb, hb, bh) in enumerate(bx.mip_layout(inf, bh0)):
            blocks = bx.deswizzle(b, off, wb, hb, bh)
            open(os.path.join(WORK, f'{n}_m{m}.astc'), 'wb').write(bx.astc_header(w, h, *inf['block']) + blocks)
            jobs.append(f'-ds {n}_m{m}.astc {n}_m{m}.png')
    open(os.path.join(WORK, 'jobs.txt'), 'w', newline='\n').write('\n'.join(jobs) + '\n')
    print(f'exported {len(jobs)} mips to {WORK}')

def recolor():
    jobs, changed_total = ([], 0)
    for t in TEXTURES:
        b, _, _ = bx.load(rel(t))
        inf = bx.info(b)
        bxs, bys = inf['block']
        n = base(t)
        cache = {}
        metal = None
        mtl_rel = 'Tex/' + n.replace('_Alb', '_Mtl') + '.bntx.zs'
        if 'Player_Adult' in n and os.path.exists(os.path.join(bx.cm.ROMFS, *mtl_rel.split('/'))):
            import bcn
            metal = bcn.decode_texture(mtl_rel)
        for m, (off, w, h, wb, hb, bh) in enumerate(bx.mip_layout(inf, pick_bh(b, inf))):
            pw, ph, px = pngio.read_png(os.path.join(WORK, f'{n}_m{m}.png'))
            assert (pw, ph) == (w, h), (t, m, pw, ph, w, h)
            mask = None
            jewel, inner, shaded, flange = (set(), set(), {}, set())
            if n == 'Mt_Weapon_Sword_Master_Dark_Alb':
                mw, mh, mpx = pngio.read_png(os.path.join(GEAR_WORK, f'Mt_Weapon_Sword_Master_Alb_m{m}.png'))
                assert (mw, mh) == (w, h)
                mask = mpx
                for yy in range(h):
                    for xx in range(w):
                        q = (yy * w + xx) * 4
                        hh, ss, vv = colorsys.rgb_to_hsv(mpx[q] / 255, mpx[q + 1] / 255, mpx[q + 2] / 255)
                        if 25 <= hh * 360 <= 60 and ss > 0.3 and (vv > 0.25):
                            jewel.add((xx, yy))
                gem_island = {p for p in jewel if p[0] < 0.9 * w}
                flange = jewel - gem_island
                inner = interior(gem_island, w, h, max(0, round(4 * w / 768)))
            if n == 'Weapon_Sword_Master':
                gem = set()
                for yy in range(436, 509):
                    for xx in range(266, 343):
                        q = (yy * w + xx) * 4
                        hh, ss, vv = colorsys.rgb_to_hsv(px[q] / 255, px[q + 1] / 255, px[q + 2] / 255)
                        cool = 180 <= hh * 360 <= 260 and ss > 0.04
                        if 272 <= xx <= 291 and 471 <= yy <= 503:
                            if not cool and vv > 0.45 and (px[q + 3] > 128):
                                jewel.add((xx, yy))
                                gem.add((xx, yy))
                        elif yy < 471 and 15 <= hh * 360 <= 60 and (ss > 0.1) and (vv > 0.3):
                            jewel.add((xx, yy))
                inner = interior(gem, w, h, 1)
                shaded = gem_shader(inner, px, w)
            out = bytearray(px)
            changed_blocks = set()
            for y in range(h):
                for x in range(w):
                    o = (y * w + x) * 4
                    if mask is not None:
                        ph, ps, pv = colorsys.rgb_to_hsv(px[o] / 255, px[o + 1] / 255, px[o + 2] / 255)
                        if (x, y) in flange:
                            new = guard_colour(pv)
                        elif (x, y) in jewel:
                            new = jewel_colour((x, y) in inner, max(px[o:o + 3]) / 255)
                        elif 60 <= ph * 360 <= 170 and ps > 0.12:
                            new = leather(pv)
                        else:
                            new = None
                        key = bytes(px[o:o + 3])
                    elif (x, y) in jewel:
                        new = shaded[x, y] if (x, y) in shaded else jewel_colour(False, max(px[o:o + 3]) / 255)
                        key = bytes(px[o:o + 3])
                    elif metal and metal[2][y * metal[1] // h][x * metal[0] // w] > 128:
                        lum = 0.3 * px[o] + 0.59 * px[o + 1] + 0.11 * px[o + 2]
                        grey = min(255, int(lum * 1.08))
                        new = (grey, grey, min(255, int(grey * 1.03)))
                        key = bytes(px[o:o + 3])
                    else:
                        key = bytes(px[o:o + 3])
                        if key not in cache:
                            cache[key] = recolor_pixel(t, px[o], px[o + 1], px[o + 2])
                        new = cache[key]
                    if new and bytes(new) != key:
                        out[o:o + 3] = bytes(new)
                        changed_blocks.add((x // bxs, y // bys))
            pngio.write_png(os.path.join(WORK, f'{n}_m{m}_new.png'), w, h, out)
            open(os.path.join(WORK, f'{n}_m{m}_changed.txt'), 'w').write('\n'.join((f'{bx_},{by_}' for bx_, by_ in sorted(changed_blocks))))
            changed_total += len(changed_blocks)
            jobs.append(f'-cs {n}_m{m}_new.png {n}_m{m}_new.astc {bxs}x{bys} -thorough')
    open(os.path.join(WORK, 'jobs.txt'), 'w', newline='\n').write('\n'.join(jobs) + '\n')
    print(f'recoloured; {changed_total} blocks changed across all mips; encode jobs written')

def do_import():
    from compression import zstd
    os.makedirs(ASSETS, exist_ok=True)
    for t in TEXTURES:
        b, dname, dicts = bx.load(rel(t))
        inf = bx.info(b)
        data = bytearray(b)
        kept = replaced = 0
        n = base(t)
        for m, (off, w, h, wb, hb, bh) in enumerate(bx.mip_layout(inf, pick_bh(b, inf))):
            orig = bx.deswizzle(b, off, wb, hb, bh)
            new = open(os.path.join(WORK, f'{n}_m{m}_new.astc'), 'rb').read()[16:]
            assert len(new) == len(orig) == wb * hb * 16
            changed = set()
            txt = open(os.path.join(WORK, f'{n}_m{m}_changed.txt')).read().split()
            for line in txt:
                a, c = line.split(',')
                changed.add((int(a), int(c)))
            merged = bytearray(orig)
            for cx, cy in changed:
                i = (cy * wb + cx) * 16
                merged[i:i + 16] = new[i:i + 16]
            replaced += len(changed)
            kept += wb * hb - len(changed)
            bx.swizzle_into(data, off, bytes(merged), wb, hb, bh)
        assert len(data) == len(b)
        packed = zstd.compress(bytes(data), level=19, zstd_dict=dicts[dname]) if dname else zstd.compress(bytes(data), 19)
        out = os.path.join(ASSETS, *rel(t).split('/'))
        os.makedirs(os.path.dirname(out), exist_ok=True)
        open(out, 'wb').write(packed)
        print(f'{t}: {replaced} blocks re-encoded, {kept} kept; wrote assets/{rel(t)} ({len(packed)} B)')
if __name__ == '__main__':
    {'export': export, 'recolor': recolor, 'import': do_import}[sys.argv[1]]()
