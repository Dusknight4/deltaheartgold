"""Applies the FireRed romhack's data changes to HeartGold. Run from the repo root:

    python3 tools/apply_firered_data.py            # dry run: prints what WOULD change, writes nothing
    python3 tools/apply_firered_data.py --apply    # writes files/poketool/personal/personal.json, waza_tbl.narc, wotbl.narc

Rules (from the project owner):
  * BASE STATS: any stat that is HIGHER in the FireRed mod than in HeartGold is set to the FireRed value (HP/Atk/Def/Spe/SpA/SpD only).
  * LEVEL-UP LEARNSETS (species 1..386): the new list is every FireRed level-up move at its FireRed level, plus every HeartGold
    level-up move that FireRed does not have, at its normal HeartGold level. (A move both games have uses the FireRed level.)
  * MOVES (Gen 3 moves only, ids 1..354): power raised where FireRed's is higher, accuracy raised where FireRed's is higher
    (0 = never misses counts as highest), type changed where it differs. PP is only changed with --pp (increases only).
    Moves that did not exist in Gen 3 are never touched. Gen 3 and Gen 4 use the same move ids 1..354.
"""
import json, re, struct, sys

APPLY = '--apply' in sys.argv
WITH_PP = '--pp' in sys.argv

FR = 'pokefirered-master/'
PERSONAL = 'files/poketool/personal/personal.json'
WAZA = 'files/poketool/waza/waza_tbl.narc'
WOTBL = 'files/poketool/personal/wotbl.narc'


# ----------------------------------------------------------------------------------------------------------- helpers
def defs(path, prefix):
    d = {}
    for line in open(path, encoding='utf-8', errors='replace'):
        m = re.match(r'#define\s+(%s[A-Z0-9_]+)\s+(\d+)\b' % prefix, line)
        if m:
            d[m.group(1)] = int(m.group(2))
    return d


class Narc:
    """Minimal NARC reader/writer that keeps every untouched member byte-identical."""
    def __init__(self, path):
        self.raw = open(path, 'rb').read()
        b = self.raw
        assert b[:4] == b'NARC', 'not a NARC'
        self.btaf = 0x10
        assert b[self.btaf:self.btaf + 4] == b'BTAF'
        self.count = struct.unpack_from('<H', b, self.btaf + 8)[0]
        btaf_size = struct.unpack_from('<I', b, self.btaf + 4)[0]
        self.btnf = self.btaf + btaf_size
        btnf_size = struct.unpack_from('<I', b, self.btnf + 4)[0]
        self.gmif = self.btnf + btnf_size
        self.btnf_block = b[self.btnf:self.gmif]
        self.data = self.gmif + 8
        self.members = []
        for i in range(self.count):
            s, e = struct.unpack_from('<II', b, self.btaf + 0xC + i * 8)
            self.members.append(bytearray(b[self.data + s:self.data + e]))
        self.header_tail = b[:0x10]

    def build(self):
        fat = b''
        body = b''
        for m in self.members:
            start = len(body)
            body += bytes(m)
            fat += struct.pack('<II', start, len(body))
            while len(body) % 4:
                body += b'\xff'   # pad members to 4 bytes (0xFF, matching common NARC tools)
        btaf = b'BTAF' + struct.pack('<IHH', 12 + len(fat), self.count, 0) + fat
        gmif = b'GMIF' + struct.pack('<I', 8 + len(body)) + body
        total = 0x10 + len(btaf) + len(self.btnf_block) + len(gmif)
        header = b'NARC' + struct.pack('<HHIHH', 0xFFFE, 0x0100, total, 0x10, 3)
        return header + btaf + self.btnf_block + gmif


def report(title, lines, limit=12):
    print('\n== %s: %d' % (title, len(lines)))
    for l in lines[:limit]:
        print('   ', l)
    if len(lines) > limit:
        print('    ...')


# ----------------------------------------------------------------------------------------------------------- 1. base stats
move_id = defs(FR + 'include/constants/moves.h', 'MOVE_')
fr_species_ids = defs(FR + 'include/constants/species.h', 'SPECIES_')

src = open(FR + 'src/data/pokemon/species_info.h', encoding='utf-8', errors='replace').read()
body = src[src.index('const struct SpeciesInfo gSpeciesInfo[]'):]
fr_stats = {}
for m in re.finditer(r'\[SPECIES_([A-Z0-9_]+)\]\s*=\s*(\{0\}|\{.*?\n    \}),', body, re.S):
    name, blk = m.group(1), m.group(2)
    if blk == '{0}':
        continue
    d = {}
    for f, key in (('baseHP', 'hp'), ('baseAttack', 'atk'), ('baseDefense', 'def'), ('baseSpeed', 'speed'),
                   ('baseSpAttack', 'spatk'), ('baseSpDefense', 'spdef'), ('expYield', 'expYield')):
        mm = re.search(r'\.%s\s*=\s*(\d+)' % f, blk)
        if mm:
            d[key] = int(mm.group(1))
    if len(d) == 7:
        fr_stats[name] = d
assert 'BULBASAUR' in fr_stats and 'NONE' not in fr_stats

raw_json = open(PERSONAL, encoding='utf-8').read()
pj = json.loads(raw_json)
# make sure we can write the file back byte-identically before we change anything
assert json.dumps(pj, indent=2, ensure_ascii=False) + '\n' == raw_json or json.dumps(pj, indent=2, ensure_ascii=False) == raw_json, \
    'personal.json does not round-trip through json.dumps(indent=2); refusing to rewrite it'
stat_lines = []
exp_lines = []
for e in pj['baseStats']:
    f = fr_stats.get(e['species'])
    if not f:
        continue
    for k, v in f.items():
        if v > e[k]:
            if k == 'expYield':
                exp_lines.append('%s expYield %d -> %d' % (e['species'], e[k], v))
            else:
                stat_lines.append('%s %s %d -> %d' % (e['species'], k, e[k], v))
            if APPLY:
                e[k] = v
report('BASE STATS raised', stat_lines, 8)
report('EXP YIELD raised', exp_lines, 8)


# ----------------------------------------------------------------------------------------------------------- 2. moves
hg_move_ids = defs('include/constants/moves.h', 'MOVE_')
types = {}
for line in open('include/constants/pokemon.h', encoding='utf-8', errors='replace'):
    m = re.match(r'#define\s+(TYPE_[A-Z]+)\s+(\d+)\b', line)
    if m:
        types[m.group(1)] = int(m.group(2))
inv_type = {v: k for k, v in types.items()}

msrc = open(FR + 'src/data/battle_moves.h', encoding='utf-8', errors='replace').read()
fr_moves = {}
for m in re.finditer(r'\[MOVE_([A-Z0-9_]+)\]\s*=\s*\{(.*?)\n    \},', msrc, re.S):
    name, blk = m.group(1), m.group(2)
    g = lambda f: re.search(r'\.%s\s*=\s*([A-Z0-9_]+)' % f, blk)
    p, t, a, pp = g('power'), g('type'), g('accuracy'), g('pp')
    if p and t and a and pp and ('MOVE_' + name) in move_id:
        fr_moves[move_id['MOVE_' + name]] = dict(name=name, power=int(p.group(1)), type=types[t.group(1)], acc=int(a.group(1)), pp=int(pp.group(1)))

waza = Narc(WAZA)
eff = lambda a: 255 if a == 0 else a
power_l, acc_l, type_l, pp_l = [], [], [], []
for mid, f in sorted(fr_moves.items()):
    if mid < 1 or mid > 354:
        continue
    m = waza.members[mid]
    power, mtype, acc, pp = m[3], m[4], m[5], m[6]
    if f['power'] > power:
        power_l.append('%s power %d -> %d' % (f['name'], power, f['power']))
        m[3] = f['power']
    if eff(f['acc']) > eff(acc):
        acc_l.append('%s accuracy %d -> %d' % (f['name'], acc, f['acc']))
        m[5] = f['acc']
    if f['type'] != mtype:
        type_l.append('%s type %s -> %s' % (f['name'], inv_type[mtype], inv_type[f['type']]))
        m[4] = f['type']
    if WITH_PP and f['pp'] > pp:
        pp_l.append('%s pp %d -> %d' % (f['name'], pp, f['pp']))
        m[6] = f['pp']
report('MOVE power raised', power_l, 6)
report('MOVE accuracy raised', acc_l, 6)
report('MOVE type changed', type_l, 6)
if WITH_PP:
    report('MOVE pp raised (--pp)', pp_l, 6)


# ----------------------------------------------------------------------------------------------------------- 3. learnsets
fr_ls_src = open(FR + 'src/data/pokemon/level_up_learnsets.h', encoding='utf-8', errors='replace').read()
arrays = {}
for m in re.finditer(r'static const u16 (s\w+LevelUpLearnset)\[\]\s*=\s*\{(.*?)\};', fr_ls_src, re.S):
    arrays[m.group(1)] = [(int(lv), move_id[mv]) for lv, mv in re.findall(r'LEVEL_UP_MOVE\(\s*(\d+)\s*,\s*(MOVE_\w+)\s*\)', m.group(2))]
ptr = dict(re.findall(r'\[(SPECIES_\w+)\]\s*=\s*(s\w+LevelUpLearnset)', open(FR + 'src/data/pokemon/level_up_learnset_pointers.h', encoding='utf-8', errors='replace').read()))
hg_species = defs('include/constants/species.h', 'SPECIES_')

wot = Narc(WOTBL)
def parse_ls(m):
    out = []
    for k in range(0, len(m) - 1, 2):
        v = struct.unpack_from('<H', m, k)[0]
        if v == 0xFFFF:
            break
        out.append((v >> 9, v & 0x1FF))
    return out

ls_changed, max_len = 0, 0
examples = []
for name, sid in fr_species_ids.items():
    if name == 'SPECIES_NONE' or sid > 411 or name not in ptr or name not in hg_species:
        continue
    hid = hg_species[name]
    if hid < 1 or hid > 386:
        continue
    fr_list = arrays[ptr[name]]
    hg_list = parse_ls(wot.members[hid])
    fr_moves_set = {mv for _, mv in fr_list}
    merged = fr_list + [(l, mv) for l, mv in hg_list if mv not in fr_moves_set]
    merged = [x for _, x in sorted(enumerate(merged), key=lambda t: (t[1][0], t[0]))]
    max_len = max(max_len, len(merged))
    if merged != hg_list:
        ls_changed += 1
        if len(examples) < 3:
            examples.append('%s: %d -> %d moves' % (name, len(hg_list), len(merged)))
        blob = b''.join(struct.pack('<H', (lv << 9) | mv) for lv, mv in merged) + b'\xff\xff'
        wot.members[hid] = bytearray(blob)
print('\n== LEARNSETS rewritten: %d species (longest merged list: %d moves)  e.g. %s' % (ls_changed, max_len, examples))
assert max_len <= 30, 'a merged list is longer than the enlarged game buffers allow'


# ----------------------------------------------------------------------------------------------------------- write + verify
if not APPLY:
    print('\nDRY RUN - nothing written. Re-run with --apply to write the files.')
    sys.exit(0)

open(PERSONAL, 'w', encoding='utf-8').write(json.dumps(pj, indent=2, ensure_ascii=False) + ('\n' if raw_json.endswith('\n') else ''))
open(WAZA, 'wb').write(waza.build())
open(WOTBL, 'wb').write(wot.build())

# verification: re-read everything and check it against what we meant to write
chk_w, chk_l = Narc(WAZA), Narc(WOTBL)
assert chk_w.count == waza.count and chk_l.count == wot.count
for i in range(chk_w.count):
    assert bytes(chk_w.members[i]) == bytes(waza.members[i]), 'waza member %d differs after write' % i
for i in range(chk_l.count):
    assert bytes(chk_l.members[i]) == bytes(wot.members[i]), 'wotbl member %d differs after write' % i
print('\nWRITTEN and re-verified: personal.json, waza_tbl.narc, wotbl.narc')
