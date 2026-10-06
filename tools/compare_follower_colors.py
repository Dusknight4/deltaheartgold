"""Compares a Pokemon's 3D FOLLOWER model colors with its 2D SPRITE colors (regular vs regular, shiny vs shiny).
Read-only analysis; touches no game files. Run from the repo root with the standalone MSYS2 python (see Coding Walkthrough).

  python3 tools/compare_follower_colors.py --mmodel 457 --narc files/a/0/0/4 --front-member 950 --pal-normal 952 --pal-shiny 953
      Totodile (pokegra: front female = 6*species+2, front male = +3, normal palette = 6*species+4, shiny = +5)
  python3 tools/compare_follower_colors.py --mmodel 716 --narc files/poketool/pokegra/otherpoke.narc --front-member 1 --pal-normal 158 --pal-shiny 159
      Deoxys Normal (otherpoke: front = 2*form+1, shared palettes 0x9E normal / 0x9F shiny - see GetMonSpriteCharAndPlttNarcIdsEx)

Follower model number = MMODEL_FOLLOWER_MON_* in include/constants/mmodel.h (file files/data/mmodel/mmodel/mmodel_<n:08d>.NSBTX).

Two reports are printed:
  1. NEAREST-COLOR match (the method of Changelog ENTRY AA): each follower palette color is paired with the closest sprite
     palette color in RGB; prints hue (sprite - follower), saturation and brightness ratios. Validated: it reproduces ENTRY AA's
     Totodile shiny body deltas (-27/-26/-20) and Feraligatr shiny (-16/-15/-17/-2). Only trustworthy when the two palettes are
     built from similar colors (match distance roughly < 60).
  2. AREA-WEIGHTED groups: counts how many pixels of the sprite (decrypted with the game's own LCRNG XOR) and of the follower
     texture use each palette color, then compares warm / cool / purple / neutral groups by pixel share. Use this when the
     palettes are laid out differently (Deoxys). Caveat: the follower is a lit 3D model, so on-screen it can look darker still.
Both views compare the SOURCE palettes; the personality hue/saturation/value rotation is applied equally to both in game.
"""
import argparse, colorsys, math, struct


def narc_members(path):
    data = open(path, 'rb').read()
    assert data[:4] == b'NARC'
    cnt = struct.unpack_from('<H', data, 0x18)[0]
    btnf = 0x10 + struct.unpack_from('<I', data, 0x14)[0]
    gmif = btnf + struct.unpack_from('<I', data, btnf + 4)[0] + 8
    out = []
    for i in range(cnt):
        s, e = struct.unpack_from('<II', data, 0x1C + i * 8)
        out.append(data[gmif + s:gmif + e])
    return out


def rgb8(c):
    return ((c & 31) * 255 // 31, ((c >> 5) & 31) * 255 // 31, ((c >> 10) & 31) * 255 // 31)


def hsv(c):
    h, s, v = colorsys.rgb_to_hsv(*[x / 255 for x in rgb8(c)])
    return h * 360, s, v


def nclr_colors(blob):
    assert blob[:4] == b'RLCN'
    p = blob.find(b'TTLP')
    n = min(struct.unpack_from('<I', blob, p + 16)[0] // 2, 16)
    return [struct.unpack_from('<H', blob, p + 24 + 2 * i)[0] for i in range(n)]


def read_tex0(path):
    b = open(path, 'rb').read()
    assert b[:4] == b'BTX0'
    tex0 = None
    for i in range(struct.unpack_from('<H', b, 14)[0]):
        off = struct.unpack_from('<I', b, 16 + 4 * i)[0]
        if b[off:off + 4] == b'TEX0':
            tex0 = off
    # TEX0 layout: +12 texture size>>3, +20 texture offset, +48 palette size>>3, +56 palette offset (relative to TEX0)
    tsz = struct.unpack_from('<H', b, tex0 + 12)[0] << 3
    tofs = struct.unpack_from('<I', b, tex0 + 20)[0]
    psz = struct.unpack_from('<I', b, tex0 + 48)[0] << 3
    pofs = struct.unpack_from('<I', b, tex0 + 56)[0]
    praw = b[tex0 + pofs: tex0 + pofs + psz]
    pal = [struct.unpack_from('<H', praw, 2 * i)[0] for i in range(len(praw) // 2)]
    tex = b[tex0 + tofs: tex0 + tofs + tsz]
    hist = [0] * 16
    for byte in tex:
        hist[byte & 15] += 1
        hist[byte >> 4] += 1
    return pal[:16], pal[16:32], hist  # slot 0 normal, slot 1 shiny, pixel-index histogram


def sprite_hist(member):
    d = list(struct.unpack('<3200H', member[-6400:]))
    seed = d[0]
    hist = [0] * 16
    for i in range(3200):
        d[i] ^= seed & 0xFFFF
        seed = (seed * 1103515245 + 24691) & 0xFFFFFFFF
        hist[d[i] & 15] += 1
        hist[(d[i] >> 4) & 15] += 1
        hist[(d[i] >> 8) & 15] += 1
        hist[(d[i] >> 12) & 15] += 1
    return hist


def hue_delta(a, b):
    return (a - b + 180) % 360 - 180


def nearest_report(title, fol, spr):
    print('  [%s] nearest-color match (fol idx -> spr idx | fol HSV | spr HSV | dH spr-fol, S ratio, V ratio, match dist)' % title)
    for i in range(1, min(16, len(fol))):
        if fol[i] == 0:
            continue
        j = min(range(1, len(spr)), key=lambda k: sum((x - y) ** 2 for x, y in zip(rgb8(fol[i]), rgb8(spr[k]))))
        hf, sf, vf = hsv(fol[i]); hs, ss, vs = hsv(spr[j])
        d = sum((x - y) ** 2 for x, y in zip(rgb8(fol[i]), rgb8(spr[j]))) ** 0.5
        gray = sf < 0.12 or ss < 0.12
        print('     %2d -> %2d | %3.0f %.2f %.2f | %3.0f %.2f %.2f | %s S%.2f V%.2f | %5.1f%s' % (
            i, j, hf, sf, vf, hs, ss, vs, 'gray ' if gray else '%+4.0f' % hue_delta(hs, hf),
            sf / ss if ss else 0, vf / vs if vs else 0, d, '  (weak match)' if d >= 60 else ''))


def group_of(h, s, v):
    if s < 0.2 or v < 0.15:
        return 'neutral (gray/black/white)'
    if h >= 330 or h < 70:
        return 'warm body (red/orange/yellow)'
    if 110 <= h <= 260:
        return 'cool (green/teal/blue)'
    return 'purple/magenta'


def groups(pal, hist):
    tot = sum(hist[1:])
    g = {}
    for i in range(1, 16):
        if hist[i] and i < len(pal):
            h, s, v = hsv(pal[i])
            g.setdefault(group_of(h, s, v), []).append((hist[i], h, s, v))
    out = {}
    for k, items in g.items():
        w = sum(c for c, *_ in items)
        hm = math.degrees(math.atan2(sum(c * math.sin(math.radians(h)) for c, h, s, v in items),
                                     sum(c * math.cos(math.radians(h)) for c, h, s, v in items))) % 360
        out[k] = (100 * w / tot, hm, sum(c * s for c, h, s, v in items) / w, sum(c * v for c, h, s, v in items) / w)
    return out


def area_report(title, fpal, fhist, spal, shist):
    F, S = groups(fpal, fhist), groups(spal, shist)
    print('  [%s] area-weighted color groups (share of non-transparent pixels, mean H S V)' % title)
    print('     %-30s | sprite share  H   S    V  | follower share  H   S    V  | dH(spr-fol)  V fol/spr  S fol/spr' % 'group')
    for k in sorted(set(F) | set(S)):
        s, f = S.get(k), F.get(k)
        a = '%5.1f%% %4.0f %.2f %.2f' % (s[0], s[1], s[2], s[3]) if s else '   (none)'
        b = '%5.1f%% %4.0f %.2f %.2f' % (f[0], f[1], f[2], f[3]) if f else '   (none)'
        c = ''
        if s and f:
            c = ('%+5.0f deg' % hue_delta(s[1], f[1]) if not k.startswith('neutral') else '     -    ') + '   %5.2f      %5.2f' % (f[3] / s[3], f[2] / s[2] if s[2] else 0)
        print('     %-30s | %-26s | %-27s | %s' % (k, a, b, c))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--mmodel', type=int, required=True)
    ap.add_argument('--narc', required=True)
    ap.add_argument('--front-member', type=int, required=True)
    ap.add_argument('--pal-normal', type=int, required=True)
    ap.add_argument('--pal-shiny', type=int, required=True)
    a = ap.parse_args()
    members = narc_members(a.narc)
    fn, fs, fhist = read_tex0('files/data/mmodel/mmodel/mmodel_%08d.NSBTX' % a.mmodel)
    shist = sprite_hist(members[a.front_member])
    for title, fpal, sp in (('REGULAR', fn, a.pal_normal), ('SHINY', fs, a.pal_shiny)):
        spal = nclr_colors(members[sp])
        print('\n=== %s follower vs %s sprite ===' % (title, title))
        nearest_report(title, fpal, spal)
        area_report(title, fpal, fhist, spal, shist)


if __name__ == '__main__':
    main()
