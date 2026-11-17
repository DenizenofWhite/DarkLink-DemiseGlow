"""Recolour the ASTC textures (sheath, clothes, Dark sword jewel, menu pictures, Goron tunic, eyes, face, hair colour table): export mips for astcenc to decode, recolour by hue/metal map/garment piece, astcenc encodes, splice only the changed blocks."""
import colorsys, os, struct, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bntx_astc as bx
import pngio
ASSETS = os.path.join(HERE, 'assets')
SETS = {'weapons': ['Mt_Weapon_Sword_Master_Alb', 'Mt_Weapon_Sheath_Master_Alb'], 'clothes': ['Mt_Vest_Player_Adult_Alb', 'Mt_Inner_Player_Adult_Alb', 'Mt_Leater_Upper_Player_Adult_Alb', 'Mt_Boots_Player_Adult_Alb', 'Mt_Glove_Player_Adult_Alb'], 'darksword': ['Mt_Weapon_Sword_Master_Dark_Alb'], 'clothes_metal': ['Mt_Leater_Upper_Player_Adult_Alb', 'Mt_Boots_Player_Adult_Alb', 'Mt_Glove_Player_Adult_Alb'], 'icons': ['UI/Tex/Icon/Weapon_Sword_Master', 'UI/Tex/Icon/Weapon_Shield_Hylian', 'UI/Tex/Icon/Armor_Adult_Normal'], 'tunics': ['Mt_Leater_Upper_Armor_Adult_Goron_Alb', 'Mt_Leater_Upper_Armor_Adult_Zora_Alb'], 'goron': ['Mt_Vest_Armor_Adult_Goron_Alb', 'Mt_Inner_Armor_Adult_Goron_Alb', 'Mt_Angin_Armor_Adult_Goron_Alb', 'Mt_HoodAcs_Armor_Adult_Goron_Alb'], 'beads': ['Mt_Beads_Armor_Adult_Goron_Alb', 'Mt_Beads_B_Armor_Adult_Goron_Alb'], 'zora': ['Mt_Vest_Armor_Adult_Zora_Alb', 'Mt_Inner_Armor_Adult_Zora_Alb', 'Mt_Angin_Armor_Adult_Zora_Alb', 'Mt_Angin_Acs_Armor_Adult_Zora_Alb', 'Mt_Parts_Armor_Adult_Zora_Alb'], 'eyes': ['Eye_Inner_Iris_CmnTex_Chara_Eye_Alb'], 'hairlut': [f'CmnTex_Chara_Hair_LUT_{c}_Gn0' for c in 'ABCDEFGZ'], 'hairlut_a': ['CmnTex_Chara_Hair_LUT_A_Gn0'], 'face': ['Mt_Face_Player_Adult_Alb'], 'icon_goron': ['UI/Tex/Icon/Armor_Adult_Goron']}
METAL_MAP = {}
SETS['tunics_goron'] = ['Mt_Leater_Upper_Armor_Adult_Goron_Alb']
WORK_ROOT = os.path.join(HERE, 'work')
WORK_DIRS = {'weapons': 'gear', 'clothes_metal': 'clothes', 'beads': 'tunics', 'tunics_goron': 'tunics', 'hairlut_a': 'hairlut'}

def use_set(s):
    global SET, TEXTURES, WORK
    SET, TEXTURES = (s, SETS[s])
    WORK = os.path.join(WORK_ROOT, WORK_DIRS.get(s, s))
use_set('weapons')
GEAR_WORK = os.path.join(WORK_ROOT, 'gear')

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
    if tex.endswith('/Icon/Armor_Adult_Goron'):
        red = (hue >= 335 or hue <= 14) and s > 0.38 and (v > 0.18)
        if red:
            return None
        lum = 0.3 * r + 0.59 * g + 0.11 * b
        if 36 <= hue <= 62 and s > 0.3 and (v > 0.6):
            grey = min(255, int(lum * 0.78))
            return (grey, grey, min(255, int(grey * 1.03)))
        if s < 0.08 and v > 0.75:
            return None
        return leather(v)
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
    if 'Eye_Inner_Iris' in tex:
        nr, ng, nb = colorsys.hsv_to_rgb(0.995, 0.96, min(1.0, v * 1.2))
        return (int(255 * nr), int(255 * ng), int(255 * nb))
    if 'Hair_LUT_' in tex:
        lum = (0.3 * r + 0.59 * g + 0.11 * b) / 255
        k = 0.6 * lum
        return (int(255 * k * 0.96), int(255 * k), min(255, int(255 * k * 1.06)))
    if 'Armor_Adult_Goron' in tex and 'Leater_Upper' not in tex:
        red = (hue >= 335 or hue <= 14) and s > 0.38 and (v > 0.18)
        lum = 0.3 * r + 0.59 * g + 0.11 * b
        black = (int(255 * (0.05 + 0.24 * lum / 255)), int(255 * (0.05 + 0.24 * lum / 255)), min(255, int(255 * (0.05 + 0.24 * lum / 255) * 1.08)))
        if 'Mt_Inner_' in tex:
            return black
        if 'Mt_Angin_' in tex:
            return None if red else black
        if 'Mt_Vest_' in tex:
            hs = hue if hue < 180 else hue - 360
            if -4 <= hs <= 14 and s > 0.3 and (v < 0.45):
                nr, ng, nb = colorsys.hsv_to_rgb(357.5 / 360, max(0.62, min(0.88, s * 1.65)), min(0.42, v * 1.85))
                return (int(255 * nr), int(255 * ng), int(255 * nb))
            if red:
                return None
            if 30 <= hue <= 62 and s > 0.12 and (v > 0.45):
                k = 0.04 + 0.12 * lum / 255
                return (int(255 * k), int(255 * k), min(255, int(255 * k * 1.08)))
            return leather(v)
        if 'Mt_Beads' in tex:
            if s < 0.1:
                shade = 0.08
            elif 40 <= hue <= 75:
                shade = 0.17
            elif 15 <= hue < 40:
                shade = 0.12
            elif hue >= 330 or hue < 15:
                shade = 0.07
            else:
                shade = 0.03
            k = shade + 0.16 * lum / 255
            return (int(255 * k), int(255 * k), int(255 * k))
        if 'Mt_HoodAcs_' in tex:
            if 38 <= hue <= 62 and s > 0.3 and (v > 0.6):
                grey = min(255, int(lum * 0.78))
                return (grey, grey, min(255, int(grey * 1.03)))
            return leather(v)
        return None
    if 'Armor_Adult_Zora' in tex and 'Leater_Upper' not in tex:
        if 'Mt_Inner_' in tex:
            lum = 0.3 * r + 0.59 * g + 0.11 * b
            k = 0.05 + 0.24 * lum / 255
            return (int(255 * k), int(255 * k), min(255, int(255 * k * 1.08)))
        if 'Mt_Vest_' in tex:
            return None if 180 <= hue <= 262 and s > 0.14 else leather(v)
        if 10 <= hue <= 50 and s > 0.15:
            return leather(v)
        return None
    if 'Armor_Adult' in tex and 'Leater_Upper' not in tex:
        return None
    if 'Leater_Upper_Armor_Adult' in tex:
        gold = 36 <= hue <= 62 and s > 0.25 and (v > 0.62)
    if 'Leater_Upper_Armor_Adult' in tex and 165 <= hue <= 200 and (s > 0.35) and (v > 0.35):
        lum = 0.3 * r + 0.59 * g + 0.11 * b
        grey = min(255, int(lum * 1.1))
        return (grey, grey, min(255, int(grey * 1.03)))
    if 'Player_Adult' in tex or 'Leater_Upper_Armor_Adult' in tex:
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
FACE_EYES = ((285 / 768, 315 / 768), (483 / 768, 315 / 768))
LINER_R, LINER_FADE = (0.045, 0.003)
LINER_RGB = (14, 12, 14)
LID_MODEL, LID_SHAPE = ('Model/Player_Adult.Player_Adult.bfres.zs', 'Upper_Eyelid_low__Mt_Face_SoftEdge')
LID_SOLID, LID_FADE = (0.27, 0.3)
LID_SOLID, LID_FADE = (0.245, 0.26)
LINER_LOWER_ONLY = True
LID_PROBE = False
LID_SHAPE_LOW = 'Lower_Eyelid_low__Mt_Face_SoftEdge'
LID_PROBE_COLOURS = [(255, 0, 0), (0, 220, 0), (0, 90, 255), (255, 230, 0), (255, 0, 255)]

def on_upper_lid(x, y, w, h):
    if not (FACE_OPTS['liner'] or FACE_OPTS['hair']):
        return False
    import bfres_uv
    return bfres_uv.edge_field(LID_MODEL, LID_SHAPE, w, h)[y * w + x] is not None

def lid_liner(x, y, w, h):
    if not FACE_OPTS['liner']:
        return 0.0
    import bfres_uv
    if bfres_uv.edge_field(LID_MODEL, LID_SHAPE_LOW, w, h)[y * w + x] is not None:
        return 1.0
    f = bfres_uv.edge_field(LID_MODEL, LID_SHAPE, w, h)[y * w + x]
    if f is None:
        return 0.0
    return 1.0 if f <= LID_SOLID else max(0.0, 1 - (f - LID_SOLID) / (LID_FADE - LID_SOLID))
FACE_OPTS = {'hair': True, 'liner': True}
ISLAND_RED = {'Mt_Vest_Armor_Adult_Goron_Alb': ('Model/Armor_Adult_Goron.Armor_Adult_Goron.bfres.zs', (377, 378))}

def island_hit(tex, ids, w, h, x, y):
    import bfres_uv
    return bfres_uv.island_mask(ids[0], tex, ids[1], w, h)[y * w + x] == 1
ROPE = 'black'
_BROW_FILL = None

def brow_fill():
    global _BROW_FILL
    if _BROW_FILL is None:
        import math
        w, h, px = pngio.read_png(os.path.join(WORK, 'Mt_Face_Player_Adult_Alb_m0.png'))
        M = 12
        x0, x1 = (int(0.305 * w) - M, int(0.695 * w) + M)
        y0, y1 = (int(0.305 * h) - M, int(0.385 * h) + M)
        W_, H_ = (x1 - x0, y1 - y0)
        S3 = math.sqrt(3)

        def grid(fn):
            return [[fn(x0 + i, y0 + j) for i in range(W_)] for j in range(H_)]

        def inbox(x, y):
            u, v = ((x + 0.5) / w, (y + 0.5) / h)
            return (0.305 <= u <= 0.475 or 0.525 <= u <= 0.695) and 0.305 <= v <= 0.385

        def chan(x, y):
            o = (y * w + x) * 4
            r_, g_, b_ = (px[o] / 255, px[o + 1] / 255, px[o + 2] / 255)
            mx, mn = (max(r_, g_, b_), min(r_, g_, b_))
            sat = (mx - mn) / max(mx, 1e-06) if mx > 0 else 0
            hue = math.degrees(math.atan2(S3 * (g_ - b_), 2 * r_ - g_ - b_)) % 360
            return (mx, sat, hue)
        C = grid(chan)
        box = grid(inbox)
        hair = [[box[j][i] and C[j][i][0] < 0.6 and (C[j][i][1] > 0.33) and (30 <= C[j][i][2] <= 55) for i in range(W_)] for j in range(H_)]

        def shift_or(a, r, outside):
            offs = [(dy, dx) for dy in range(-r, r + 1) for dx in range(-r, r + 1) if dx * dx + dy * dy <= r * r]
            return [[any((a[j - dy][i - dx] if 0 <= j - dy < H_ and 0 <= i - dx < W_ else outside for dy, dx in offs)) for i in range(W_)] for j in range(H_)]
        m = shift_or(hair, 4, False)
        notm = shift_or([[not q for q in row] for row in m], 3, True)
        m = [[not notm[j][i] and box[j][i] for i in range(W_)] for j in range(H_)]
        nr = shift_or(m, 2, False)
        near = [[nr[j][i] and box[j][i] for i in range(W_)] for j in range(H_)]

        def blur(a, n):
            for _ in range(n):
                g = lambda j, i: a[j][i] if 0 <= j < H_ and 0 <= i < W_ else 0.0
                a = [[(a[j][i] + g(j - 1, i) + g(j + 1, i) + g(j, i - 1) + g(j, i + 1)) / 5 for i in range(W_)] for j in range(H_)]
            return a
        nb = blur([[1.0 if q else 0.0 for q in row] for row in near], 1)
        stroke = []
        for j in range(H_):
            row = []
            for i in range(W_):
                mx, _, hue = C[j][i]
                s = min(1.0, max(0.0, (0.56 - mx) / 0.12)) ** 0.85
                s = s * (min(1.0, max(0.0, (hue - 27) / 5)) * (1.0 if hue <= 58 else 0.0))
                row.append(s * nb[j][i])
            stroke.append(row)
        bs, bm = (blur(stroke, 3), blur([[1.0 if q else 0.0 for q in row] for row in m], 2))
        fill = [[max(stroke[j][i], 0.28 * min(1.0, max(0.0, bs[j][i] * 1.6)) * bm[j][i]) for i in range(W_)] for j in range(H_)]
        _BROW_FILL = (x0, y0, W_, H_, w, h, fill)
    return _BROW_FILL

def brow_value(u, v):
    x0, y0, W_, H_, w, h, fill = brow_fill()
    i, j = (min(w - 1, int(u * w)) - x0, min(h - 1, int(v * h)) - y0)
    return fill[j][i] if 0 <= i < W_ and 0 <= j < H_ else 0.0

def face_pixel(u, v, r, g, b):
    h, s, val = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    hue = h * 360
    lum = (0.3 * r + 0.59 * g + 0.11 * b) / 255
    cur = (r, g, b)
    if FACE_OPTS['hair'] and v < 0.73:
        t = max(0.0, min(1.0, (0.57 - val) / 0.07)) * max(0.0, min(1.0, (s - 0.36) / 0.12)) * (1.0 if 22 <= hue <= 50 else 0.0)
        d = abs(u - 0.5)
        band = 0.385 - max(0.0, min(1.0, (d - 0.05) / 0.15)) * 0.037
        if band <= v <= 0.43:
            t *= max(0.0, min(1.0, (hue - 30) / 4))
        if any((x0 <= u <= x1 and 0.305 <= v <= 0.385 for x0, x1 in ((0.305, 0.475), (0.525, 0.695)))):
            edge = max(0.0, min(1.0, (0.385 - v) / 0.015))
            t = max(t, edge * max(0.0, min(1.0, (0.645 - val) / 0.05)) * max(0.0, min(1.0, (s - 0.25) / 0.1)) * max(0.0, min(1.0, (hue - 30) / 4)) * (1.0 if hue <= 55 else 0.0))
        fill = brow_value(u, v)
        if any((abs(u - cx) <= 0.068 and 0.3 <= v <= 0.44 for cx, _ in FACE_EYES)):
            t = fill
        else:
            t = max(t, fill)
        if t > 0:
            k = 0.01 + 0.055 * lum
            blk = (255 * k * 0.92, 255 * k, 255 * k * 1.25)
            cur = tuple((c * (1 - t) + d * t for c, d in zip(cur, blk)))
    dark = 0.0
    for cx, cy in FACE_EYES if FACE_OPTS['liner'] else ():
        dx, dy = (u - cx, v - cy)
        rr = (dx * dx + dy * dy) ** 0.5
        ring = 1.0 if rr <= LINER_R else max(0.0, 1 - (rr - LINER_R) / LINER_FADE)
        if LINER_LOWER_ONLY:
            ring *= max(0.0, min(1.0, (dy + 0.004) / 0.008))
        dark = max(dark, ring)
    if dark > 0:
        liner = (14, 12, 14)
        cur = tuple((c * (1 - dark) + d * dark for c, d in zip(cur, liner)))
    out = tuple((int(max(0, min(255, c))) for c in cur))
    return None if out == (r, g, b) else out

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
        mtl_rel = 'Tex/' + METAL_MAP.get(n, n.replace('_Alb', '_Mtl')) + '.bntx.zs'
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
                    elif metal and (lambda m: m[0] if isinstance(m, tuple) else m)(metal[2][y * metal[1] // h][x * metal[0] // w]) > 128:
                        lum = 0.3 * px[o] + 0.59 * px[o + 1] + 0.11 * px[o + 2]
                        grey = min(255, int(lum * 1.08))
                        new = (grey, grey, min(255, int(grey * 1.03)))
                        key = bytes(px[o:o + 3])
                    else:
                        key = bytes(px[o:o + 3])
                        if key not in cache:
                            cache[key] = recolor_pixel(t, px[o], px[o + 1], px[o + 2])
                        new = cache[key]
                        if n == 'Mt_Vest_Armor_Adult_Goron_Alb' and 0.6 * h <= y < 0.9 * h:
                            hh, ss, vv2 = colorsys.rgb_to_hsv(px[o] / 255, px[o + 1] / 255, px[o + 2] / 255)
                            hs2 = hh * 360 if hh * 360 < 180 else hh * 360 - 360
                            if -3 <= hs2 <= 14 and 0.15 < ss <= 0.3 and (vv2 < 0.45):
                                nr, ng, nb = colorsys.hsv_to_rgb(357.5 / 360, max(0.62, min(0.88, ss * 1.65)), min(0.42, vv2 * 1.85))
                                new = (int(255 * nr), int(255 * ng), int(255 * nb))
                        if ROPE != 'speckle' and n == 'Mt_Vest_Armor_Adult_Goron_Alb' and (0.832 * h <= y < 0.866 * h) and (0.19 * w <= x < 0.81 * w):
                            lum = (0.3 * px[o] + 0.59 * px[o + 1] + 0.11 * px[o + 2]) / 255
                            if ROPE == 'red':
                                nr, ng, nb = colorsys.hsv_to_rgb(357.5 / 360, 0.78, min(0.6, 0.16 + 0.42 * lum))
                                new = (int(255 * nr), int(255 * ng), int(255 * nb))
                            else:
                                k = 0.03 + 0.14 * lum
                                new = (int(255 * k), int(255 * k), min(255, int(255 * k * 1.08)))
                        if False and n == 'Mt_Vest_Armor_Adult_Goron_Alb' and (0.09 * w <= x < 0.2 * w) and (0.785 * h <= y < 0.86 * h):
                            hh, ss, vv2 = colorsys.rgb_to_hsv(px[o] / 255, px[o + 1] / 255, px[o + 2] / 255)
                            if ss < 0.3 and vv2 < 0.3:
                                lum = (0.3 * px[o] + 0.59 * px[o + 1] + 0.11 * px[o + 2]) / 255
                                nr, ng, nb = colorsys.hsv_to_rgb(357.5 / 360, 0.76, min(0.42, 0.22 + 0.9 * lum))
                                new = (int(255 * nr), int(255 * ng), int(255 * nb))
                        if False and n == 'Mt_Vest_Armor_Adult_Goron_Alb' and (y >= 0.86 * h) and (not ((x < 0.06 * w or x >= 0.94 * w) and y >= 0.86 * h)):
                            hh, ss, vv2 = colorsys.rgb_to_hsv(px[o] / 255, px[o + 1] / 255, px[o + 2] / 255)
                            hs2 = hh * 360 if hh * 360 < 180 else hh * 360 - 360
                            if -20 <= hs2 <= 2 and 0.1 < ss < 0.45 and (vv2 >= 0.215):
                                nr, ng, nb = colorsys.hsv_to_rgb(357.5 / 360, 0.76, min(0.42, vv2 * 1.55))
                                new = (int(255 * nr), int(255 * ng), int(255 * nb))
                        if False and n == 'Mt_Vest_Armor_Adult_Goron_Alb' and (y >= 0.86 * h and (not 0.89 * h <= y < 0.915 * h) or (x < 0.18 * w and 0.55 * h <= y < 0.86 * h)) and (not ((x < 0.06 * w or x >= 0.94 * w) and y >= 0.86 * h)):
                            hh, ss, vv2 = colorsys.rgb_to_hsv(px[o] / 255, px[o + 1] / 255, px[o + 2] / 255)
                            hs2 = hh * 360 if hh * 360 < 180 else hh * 360 - 360
                            if -20 <= hs2 <= 2 and 0.1 < ss < 0.45 and (vv2 < 0.215):
                                nr, ng, nb = colorsys.hsv_to_rgb(357.5 / 360, 0.76, min(0.42, vv2 * 1.9))
                                new = (int(255 * nr), int(255 * ng), int(255 * nb))
                        if False and n == 'Mt_Vest_Armor_Adult_Goron_Alb' and (x < 0.095 * w) and (0.62 * h <= y < 0.88 * h):
                            hh, ss, vv2 = colorsys.rgb_to_hsv(px[o] / 255, px[o + 1] / 255, px[o + 2] / 255)
                            hs2 = hh * 360 if hh * 360 < 180 else hh * 360 - 360
                            if -20 <= hs2 <= 2 and 0.1 < ss < 0.45 and (vv2 < 0.215):
                                nr, ng, nb = colorsys.hsv_to_rgb(357.5 / 360, 0.76, min(0.42, vv2 * 1.9))
                                new = (int(255 * nr), int(255 * ng), int(255 * nb))
                        if n == 'Mt_Vest_Armor_Adult_Goron_Alb' and 0.18 * w <= x < 0.82 * w and (y < 0.36 * h):
                            hh, ss, vv2 = colorsys.rgb_to_hsv(px[o] / 255, px[o + 1] / 255, px[o + 2] / 255)
                            if (hh * 360 >= 335 or hh * 360 <= 14) and ss > 0.5 and (vv2 >= 0.33):
                                new = leather(vv2)
                        if n == 'Mt_Vest_Armor_Adult_Goron_Alb' and (x >= 0.885 * w and y < 0.36 * h or (x < 0.11 * w and 0.06 * h <= y < 0.36 * h)):
                            hh, ss, vv2 = colorsys.rgb_to_hsv(px[o] / 255, px[o + 1] / 255, px[o + 2] / 255)
                            if (hh * 360 >= 335 or hh * 360 <= 14) and ss > 0.15:
                                new = leather(vv2)
                        if n in ISLAND_RED and island_hit(n, ISLAND_RED[n], w, h, x, y):
                            hh, ss, vv2 = colorsys.rgb_to_hsv(px[o] / 255, px[o + 1] / 255, px[o + 2] / 255)
                            nr, ng, nb = colorsys.hsv_to_rgb(357.5 / 360, max(0.62, min(0.88, ss * 1.65)), min(0.42, vv2 * 1.85))
                            new = (int(255 * nr), int(255 * ng), int(255 * nb))
                        if n == 'Mt_HoodAcs_Armor_Adult_Goron_Alb' and x >= 0.4 * w and (0.14 * h <= y < 0.26 * h):
                            lum = 0.3 * px[o] + 0.59 * px[o + 1] + 0.11 * px[o + 2]
                            grey = min(255, int(lum * 0.95))
                            new = (grey, grey, min(255, int(grey * 1.03)))
                        if n == 'Mt_HoodAcs_Armor_Adult_Goron_Alb' and y < 0.135 * h:
                            lum = 0.3 * px[o] + 0.59 * px[o + 1] + 0.11 * px[o + 2]
                            grey = min(255, int(lum * 0.95))
                            new = (grey, grey, min(255, int(grey * 1.03)))
                        if n == 'Mt_HoodAcs_Armor_Adult_Goron_Alb' and x < 0.33 * w and (y > 0.635 * h):
                            hh, ss, vv2 = colorsys.rgb_to_hsv(px[o] / 255, px[o + 1] / 255, px[o + 2] / 255)
                            if 22 <= hh * 360 <= 70 and ss > 0.08:
                                grey = min(255, int((0.3 * px[o] + 0.59 * px[o + 1] + 0.11 * px[o + 2]) * 0.78))
                                new = (grey, grey, min(255, int(grey * 1.03)))
                        if n == 'Mt_Leater_Upper_Armor_Adult_Goron_Alb' and y >= 0.785 * h and (x >= 0.515 * w) and (not (x > 0.74 * w and y < 0.812 * h)):
                            hh, ss, vv2 = colorsys.rgb_to_hsv(px[o] / 255, px[o + 1] / 255, px[o + 2] / 255)
                            if 28 <= hh * 360 <= 70 and ss > 0.08:
                                grey = min(255, int((0.3 * px[o] + 0.59 * px[o + 1] + 0.11 * px[o + 2]) * 1.1))
                                new = (grey, grey, min(255, int(grey * 1.03)))
                        if n == 'Armor_Adult_Goron' and px[o + 3] > 0:
                            uu, vv = ((x + 0.5) / w, (y + 0.5) / h)
                            hh, ss, vv2 = colorsys.rgb_to_hsv(px[o] / 255, px[o + 1] / 255, px[o + 2] / 255)
                            lum = 0.3 * px[o] + 0.59 * px[o + 1] + 0.11 * px[o + 2]
                            if vv < 0.4 and 0.22 < uu < 0.78 and (20 <= hh * 360 <= 60) and (ss > 0.25):
                                k = 0.05 + 0.24 * lum / 255
                                new = (int(255 * k), int(255 * k), min(255, int(255 * k * 1.08)))
                            elif 0.05 <= ((uu - 0.503) ** 2 + (vv - 0.855) ** 2) ** 0.5 < 0.092:
                                if 25 <= hh * 360 <= 70 and ss < 0.5:
                                    grey = min(255, int(lum * 1.15))
                                    new = (grey, grey, min(255, int(grey * 1.03)))
                        if n == 'Mt_Face_Player_Adult_Alb':
                            new = face_pixel(x / w, y / h, px[o], px[o + 1], px[o + 2])
                            if on_upper_lid(x, y, w, h):
                                new = None
                            k = lid_liner(x, y, w, h)
                            if LID_PROBE:
                                import bfres_uv
                                f = bfres_uv.edge_field(LID_MODEL, LID_SHAPE, w, h)[y * w + x]
                                lo = bfres_uv.edge_field(LID_MODEL, LID_SHAPE_LOW, w, h)[y * w + x]
                                if f is not None:
                                    new = LID_PROBE_COLOURS[min(4, int(f * 5))]
                                elif lo is not None:
                                    new = (255, 255, 255)
                                for cx, cy in FACE_EYES:
                                    if ((x / w - cx) ** 2 + (y / h - cy) ** 2) ** 0.5 <= LINER_R + LINER_FADE:
                                        new = (0, 255, 255) if y / h < cy else (255, 140, 0)
                                k = 0
                            if k > 0:
                                new = tuple((int(c * (1 - k) + d * k) for c, d in zip(new or tuple(px[o:o + 3]), LINER_RGB)))
                        if new and n.startswith('Eye_Inner_Iris'):
                            rr = (((x + 0.5) / w - 0.5) ** 2 + ((y + 0.5) / h - 0.5) ** 2) ** 0.5
                            f = 0.06 if rr <= 0.11 else min(1.0, 0.06 + 0.94 * (rr - 0.11) / 0.05)
                            new = tuple((int(c * f) for c in new))
                        if n == 'Armor_Adult_Goron' and (w, h) == (341, 341):
                            import icon_cloth
                            if icon_cloth.mask()[y * w + x]:
                                new = icon_cloth.cloth(px[o], px[o + 1], px[o + 2])
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
