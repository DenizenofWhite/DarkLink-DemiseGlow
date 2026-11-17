"""BC7 block decoder (all modes) and a mode-6 encoder, pure Python."""
P2 = ['0011001100110011', '0001000100010001', '0111011101110111', '0001001100110111', '0000000100010011', '0011011101111111', '0001001101111111', '0000000100110111', '0000000000010011', '0011011111111111', '0000000101111111', '0000000000010111', '0001011111111111', '0000000011111111', '0000111111111111', '0000000000001111', '0000100011101111', '0111000100000000', '0000000010001110', '0111001100010000', '0011000100000000', '0000100011001110', '0000000010001100', '0111001100110001', '0011000100010000', '0000100010001100', '0110011001100110', '0011011001101100', '0001011111101000', '0000111111110000', '0111000110001110', '0011100110011100', '0101010101010101', '0000111100001111', '0101101001011010', '0011001111001100', '0011110000111100', '0101010110101010', '0110100101101001', '0101101010100101', '0111001111001110', '0001001111001000', '0011001001001100', '0011101111011100', '0110100110010110', '0011110011000011', '0110011010011001', '0000011001100000', '0100111001000000', '0010011100100000', '0000001001110010', '0000010011100100', '0110110010010011', '0011011011001001', '0110001110011100', '0011100111000110', '0110110011001001', '0110001100111001', '0111111010000001', '0001100011100111', '0000111100110011', '0011001111110000', '0010001011101110', '0100010001110111']
P3 = ['0011001102212222', '0001001122112221', '0000200122112211', '0222002200110111', '0000000011221122', '0011001100220022', '0022002211111111', '0011001122112211', '0000000011112222', '0000111111112222', '0000111122222222', '0012001200120012', '0112011201120112', '0122012201220122', '0011011211221222', '0011200122002220', '0001001101121122', '0111001120012200', '0000112211221122', '0022002200221111', '0111011102220222', '0001000122212221', '0000001101220122', '0000110022102210', '0122012200110000', '0012001211222222', '0110122112210110', '0000011012211221', '0022110211020022', '0110011020022222', '0011012201220011', '0000200022112221', '0000000211221222', '0222002200120011', '0011001200220222', '0120012001200120', '0000111122220000', '0120120120120120', '0120201212010120', '0011220011220011', '0011112222000011', '0101010122222222', '0000000021212121', '0022112200221122', '0022001100220011', '0220122102201221', '0101222222220101', '0000212121212121', '0101010101012222', '0222011102220111', '0002111200021112', '0000211221122112', '0222011101110222', '0002111211120002', '0110011001102222', '0000000021122112', '0110011022222222', '0022001100110022', '0022112211220022', '0000000000002112', '0002000100020001', '0222122202221222', '0101222222222222', '0111201122012220']
A2 = [15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 2, 8, 2, 2, 8, 8, 15, 2, 8, 2, 2, 8, 8, 2, 2, 15, 15, 6, 8, 2, 8, 15, 15, 2, 8, 2, 2, 2, 15, 15, 6, 6, 2, 6, 8, 15, 15, 2, 2, 15, 15, 15, 15, 15, 2, 2, 15]
A3B = [3, 3, 15, 15, 8, 3, 15, 15, 8, 8, 6, 6, 6, 5, 3, 3, 3, 3, 8, 15, 3, 3, 6, 10, 5, 8, 8, 6, 8, 5, 15, 15, 8, 15, 3, 5, 6, 10, 8, 15, 15, 3, 15, 5, 15, 15, 15, 15, 3, 15, 5, 5, 5, 8, 5, 10, 5, 10, 8, 13, 15, 12, 3, 3]
A3C = [15, 8, 8, 3, 15, 15, 3, 8, 15, 15, 15, 15, 15, 15, 15, 8, 15, 8, 15, 3, 15, 8, 15, 8, 3, 15, 6, 10, 15, 15, 10, 8, 15, 3, 15, 10, 10, 8, 9, 10, 6, 15, 8, 15, 3, 6, 6, 8, 15, 3, 15, 15, 15, 15, 15, 15, 15, 15, 15, 15, 3, 15, 15, 8]
W = {2: [0, 21, 43, 64], 3: [0, 9, 18, 27, 37, 46, 55, 64], 4: [0, 4, 9, 13, 17, 21, 26, 30, 34, 38, 43, 47, 51, 55, 60, 64]}
MODES = [(3, 4, 0, 0, 4, 0, 1, 0, 3, 0), (2, 6, 0, 0, 6, 0, 0, 1, 3, 0), (3, 6, 0, 0, 5, 0, 0, 0, 2, 0), (2, 6, 0, 0, 7, 0, 1, 0, 2, 0), (1, 0, 2, 1, 5, 6, 0, 0, 2, 3), (1, 0, 2, 0, 7, 8, 0, 0, 2, 2), (1, 0, 0, 0, 7, 7, 1, 0, 4, 0), (2, 6, 0, 0, 5, 5, 1, 0, 2, 0)]

def _expand(v, n):
    v <<= 8 - n
    return v | v >> n

def decode_block(b):
    v = int.from_bytes(b, 'little')
    mode = 0
    while mode < 8 and (not v >> mode & 1):
        mode += 1
    if mode == 8:
        return [(0, 0, 0, 0)] * 16
    ns, pb, rb, isb, cb, ab, epb, spb, ib, ib2 = MODES[mode]
    pos = mode + 1

    def take(n):
        nonlocal pos
        x = v >> pos & (1 << n) - 1
        pos += n
        return x
    part, rot, isel = (take(pb), take(rb), take(isb))
    ne = ns * 2
    ep = [[0, 0, 0, 255] for _ in range(ne)]
    for ch in range(3):
        for e in range(ne):
            ep[e][ch] = take(cb)
    if ab:
        for e in range(ne):
            ep[e][3] = take(ab)
    if epb:
        pbits = [take(1) for _ in range(ne)]
    elif spb:
        s = [take(1) for _ in range(ns)]
        pbits = [s[e // 2] for e in range(ne)]
    else:
        pbits = None
    for e in range(ne):
        for ch in range(4 if ab else 3):
            n = cb if ch < 3 else ab
            x = ep[e][ch]
            if pbits is not None:
                x, n = (x << 1 | pbits[e], n + 1)
            ep[e][ch] = _expand(x, n)
    if ns == 1:
        subset, anchors = ([0] * 16, {0})
    elif ns == 2:
        subset, anchors = ([int(c) for c in P2[part]], {0, A2[part]})
    else:
        subset, anchors = ([int(c) for c in P3[part]], {0, A3B[part], A3C[part]})
    idx = [take(ib - 1 if i in anchors else ib) for i in range(16)]
    idx2 = [take(ib2 - 1 if i == 0 else ib2) for i in range(16)] if ib2 else None
    out = []
    for i in range(16):
        e0, e1 = (ep[2 * subset[i]], ep[2 * subset[i] + 1])
        if idx2 is None:
            wc = wa = W[ib][idx[i]]
        elif isel:
            wc, wa = (W[ib2][idx2[i]], W[ib][idx[i]])
        else:
            wc, wa = (W[ib][idx[i]], W[ib2][idx2[i]])
        px = [(64 - wc) * e0[c] + wc * e1[c] + 32 >> 6 for c in range(3)]
        px.append((64 - wa) * e0[3] + wa * e1[3] + 32 >> 6)
        if rot:
            px[3], px[rot - 1] = (px[rot - 1], px[3])
        out.append(tuple(px))
    return out

def _quant(e):
    best = None
    for p in (0, 1):
        c7 = [min(127, max(0, int(round((x - p) / 2)))) for x in e]
        err = sum((abs(c * 2 + p - x) for c, x in zip(c7, e)))
        if best is None or err < best[2]:
            best = (c7, p, err)
    return (best[0], best[1])

def _palette(c0, p0, c1, p1):
    e0 = [c * 2 + p0 for c in c0]
    e1 = [c * 2 + p1 for c in c1]
    return [tuple(((64 - w) * a + w * b + 32 >> 6 for a, b in zip(e0, e1))) for w in W[4]]

def _indices(px, pal):
    idx, tot = ([], 0)
    for p in px:
        best, bi = (None, 0)
        for k, q in enumerate(pal):
            d = (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2 + (p[3] - q[3]) ** 2
            if best is None or d < best:
                best, bi = (d, k)
        idx.append(bi)
        tot += best
    return (idx, tot)

def encode_mode6(px):
    n = 16.0
    mean = [sum((p[c] for p in px)) / n for c in range(4)]
    cen = [[p[c] - mean[c] for c in range(4)] for p in px]
    cov = [[sum((r[i] * r[j] for r in cen)) for j in range(4)] for i in range(4)]
    axis = [1.0, 1.0, 1.0, 1.0]
    for _ in range(8):
        nxt = [sum((cov[i][j] * axis[j] for j in range(4))) for i in range(4)]
        m = max((abs(x) for x in nxt))
        if m < 1e-12:
            break
        axis = [x / m for x in nxt]
    ln = sum((x * x for x in axis)) ** 0.5
    axis = [x / ln for x in axis] if ln > 1e-12 else [0.5, 0.5, 0.5, 0.5]
    t = [sum((r[c] * axis[c] for c in range(4))) for r in cen]
    lo, hi = (min(t), max(t))
    e0 = [min(255.0, max(0.0, mean[c] + lo * axis[c])) for c in range(4)]
    e1 = [min(255.0, max(0.0, mean[c] + hi * axis[c])) for c in range(4)]
    c0, p0 = _quant(e0)
    c1, p1 = _quant(e1)
    idx, err = _indices(px, _palette(c0, p0, c1, p1))
    w = [W[4][k] / 64.0 for k in idx]
    aa = sum(((1 - x) ** 2 for x in w))
    bb = sum((x * x for x in w))
    ab = sum(((1 - x) * x for x in w))
    det = aa * bb - ab * ab
    if abs(det) > 1e-09:
        f0, f1 = ([], [])
        for c in range(4):
            sa = sum(((1 - x) * p[c] for x, p in zip(w, px)))
            sb = sum((x * p[c] for x, p in zip(w, px)))
            f0.append(min(255.0, max(0.0, (bb * sa - ab * sb) / det)))
            f1.append(min(255.0, max(0.0, (aa * sb - ab * sa) / det)))
        d0, q0 = _quant(f0)
        d1, q1 = _quant(f1)
        idx2, err2 = _indices(px, _palette(d0, q0, d1, q1))
        if err2 < err:
            c0, p0, c1, p1, idx = (d0, q0, d1, q1, idx2)
    if idx[0] >= 8:
        c0, c1, p0, p1 = (c1, c0, p1, p0)
        idx = [15 - k for k in idx]
    v, pos = (1 << 6, 7)
    for c in range(4):
        v |= c0[c] << pos
        pos += 7
        v |= c1[c] << pos
        pos += 7
    v |= p0 << pos
    v |= p1 << pos + 1
    pos += 2
    v |= idx[0] << pos
    pos += 3
    for k in idx[1:]:
        v |= k << pos
        pos += 4
    return v.to_bytes(16, 'little')
