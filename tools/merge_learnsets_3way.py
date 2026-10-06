"""Rebuilds HeartGold's level-up learnsets as a UNION of three sources, superseding ENTRY AE's
"FireRed replaces on shared move" rule with "keep every source's (level, move) pair, including a
move learned at two different levels from two different sources."

Sources (species 1..386, matching ENTRY AE's own stated scope):
  A. Vanilla HeartGold - read from the PRESERVED PRE-MERGE BACKUP (backups/2026-09-21_data-v0_pre-
     firered-data/files_poketool_personal/wotbl.narc), NOT the current wotbl.narc (which already
     has ENTRY AE's FireRed-replaces-shared-moves merge baked in - starting from that would silently
     keep discarding HG's own original levels for every shared move, exactly the bug being fixed).
  B. The user's custom FireRed romhack - pokefirered-master/src/data/pokemon/level_up_learnsets.h
     (+ level_up_learnset_pointers.h), species 1..386 (FireRed's own Gen 1-3 roster).
  C. The user's custom Crystal romhack (UltimateCrystal-master) - data/pokemon/evos_attacks.asm,
     species 1..251 (Crystal's Gen 1-2 roster; Gen 3 species 252..386 have no Crystal entry, so C is
     just skipped for them - the merge below degrades to A+B there, matching ENTRY AE's own scope note
     that Crystal cannot cover species it never had).

Merge rule (from the project owner, superseding ENTRY AE section 3): the new list is the UNION of
sources A, B and C's (level, move) pairs. A move appearing at the SAME level in more than one source
is listed once; a move appearing at DIFFERENT levels in different sources is listed at EACH of those
levels (learnable twice), NOT collapsed to a single "winning" source's level the way ENTRY AE's rule
did. Sorted by level (stable - ties keep source order A, then B, then C, then original position).

Species/move ID matching is done entirely by NUMERIC ID (never by name), reusing the exact same
verified mapping ENTRY AE's tools/apply_firered_data.py already established for FireRed<->HeartGold
(species.h/moves.h #define values, confirmed identical between the two decomp projects), plus a new
name->id map for Crystal (Gen 1/2 move ids have been numerically stable since Crystal - spot-checked
SCRATCH=10, LEER=43, BITE=44, WATER_GUN=55, HYDRO_PUMP=56, RAGE=99, all matching HeartGold's own
MOVE_* values exactly - and Crystal's evos_attacks.asm entries are already in National Dex order,
confirmed against Mewtwo(150)/Mew(151)/Chikorita(152).../Totodile(158), so file position doubles as
the species id with no separate lookup table needed).

Run from the repo root (pokeheartgold-master/):
    python3 tools/merge_learnsets_3way.py            # dry run: prints what WOULD change, writes nothing
    python3 tools/merge_learnsets_3way.py --apply    # writes files/poketool/personal/wotbl.narc
"""
import re, struct, sys

APPLY = '--apply' in sys.argv

FR = 'pokefirered-master/'
CRY = 'UltimateCrystal-master/'
WOTBL = 'files/poketool/personal/wotbl.narc'
VANILLA_WOTBL = 'backups/2026-09-21_data-v0_pre-firered-data/files_poketool_personal/wotbl.narc'


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
        assert b[:4] == b'NARC', 'not a NARC: %s' % path
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

    def build(self):
        fat = b''
        body = b''
        for m in self.members:
            start = len(body)
            body += bytes(m)
            fat += struct.pack('<II', start, len(body))
            while len(body) % 4:
                body += b'\xff'
        btaf = b'BTAF' + struct.pack('<IHH', 12 + len(fat), self.count, 0) + fat
        gmif = b'GMIF' + struct.pack('<I', 8 + len(body)) + body
        total = 0x10 + len(btaf) + len(self.btnf_block) + len(gmif)
        header = b'NARC' + struct.pack('<HHIHH', 0xFFFE, 0x0100, total, 0x10, 3)
        return header + btaf + self.btnf_block + gmif


def parse_ls(m):
    out = []
    for k in range(0, len(m) - 1, 2):
        v = struct.unpack_from('<H', m, k)[0]
        if v == 0xFFFF:
            break
        out.append((v >> 9, v & 0x1FF))
    return out


def report(title, lines, limit=12):
    print('\n== %s: %d' % (title, len(lines)))
    for l in lines[:limit]:
        print('   ', l)
    if len(lines) > limit:
        print('    ...')


# --------------------------------------------------------------------------------------- source A: vanilla HG
hg_species = defs('include/constants/species.h', 'SPECIES_')
vanilla_wot = Narc(VANILLA_WOTBL)


# --------------------------------------------------------------------------------------- source B: custom FireRed
move_id = defs(FR + 'include/constants/moves.h', 'MOVE_')
fr_species_ids = defs(FR + 'include/constants/species.h', 'SPECIES_')

fr_ls_src = open(FR + 'src/data/pokemon/level_up_learnsets.h', encoding='utf-8', errors='replace').read()
fr_arrays = {}
for m in re.finditer(r'static const u16 (s\w+LevelUpLearnset)\[\]\s*=\s*\{(.*?)\};', fr_ls_src, re.S):
    fr_arrays[m.group(1)] = [(int(lv), move_id[mv]) for lv, mv in re.findall(r'LEVEL_UP_MOVE\(\s*(\d+)\s*,\s*(MOVE_\w+)\s*\)', m.group(2))]
fr_ptr = dict(re.findall(r'\[(SPECIES_\w+)\]\s*=\s*(s\w+LevelUpLearnset)', open(FR + 'src/data/pokemon/level_up_learnset_pointers.h', encoding='utf-8', errors='replace').read()))


# --------------------------------------------------------------------------------------- source C: custom Crystal
cry_move_names = []  # index == move id
found = False
for line in open(CRY + 'constants/move_constants.asm', encoding='utf-8', errors='replace'):
    if 'const_def' in line:
        found = True
        continue
    if not found:
        continue
    m = re.match(r'\s*const\s+([A-Za-z0-9_]+)', line)
    if m:
        cry_move_names.append(m.group(1))
# sanity check (would have caught a wrong file/format immediately): known Gen 1/2 move ids
assert cry_move_names[10] == 'SCRATCH' and cry_move_names[55] == 'WATER_GUN' and cry_move_names[99] == 'RAGE', \
    'Crystal move_constants.asm layout looks different than expected: %r' % cry_move_names[:5]
cry_move_id = {name: i for i, name in enumerate(cry_move_names)}

cry_src = open(CRY + 'data/pokemon/evos_attacks.asm', encoding='utf-8', errors='replace').read()
# Position-based split (label boundaries only) instead of a non-greedy multi-line regex capture -
# more robust against edge-of-file / missing-trailing-newline quirks (a first attempt using
# "(?:.*\n)*?...(?=next label|\Z)" silently dropped one entry - Celebi, the very last label - for
# exactly this reason).
label_re = re.compile(r'^\w+EvosAttacks:\s*$', re.M)
starts = [m.start() for m in label_re.finditer(cry_src)]
starts.append(len(cry_src))
cry_lists = []  # index 0 unused, index N = species N's list (file order == National Dex order, verified)
for i in range(len(starts) - 1):
    block = cry_src[starts[i]:starts[i + 1]]
    moves = []
    for lvl, name in re.findall(r'db\s+(\d+),\s*([A-Za-z0-9_]+)\s*(?:;.*)?$', block, re.M):
        if name in cry_move_id:
            moves.append((int(lvl), cry_move_id[name]))
    cry_lists.append(moves)
print('Crystal: parsed %d species entries (expect 251)' % len(cry_lists))
assert len(cry_lists) == 251, 'expected exactly 251 Crystal species entries, got %d' % len(cry_lists)


# --------------------------------------------------------------------------------------- merge
wot = Narc(WOTBL)  # this is what gets overwritten; only used for its member SIZES/count, not its content
changed, max_len = 0, 0
examples = []
length_hist = []

for name, sid in sorted(fr_species_ids.items(), key=lambda kv: kv[1]):
    if name == 'SPECIES_NONE' or name not in fr_ptr or name not in hg_species:
        continue
    hid = hg_species[name]
    if hid < 1 or hid > 386:
        continue

    a_list = parse_ls(vanilla_wot.members[hid])          # source A: vanilla HG
    b_list = fr_arrays[fr_ptr[name]]                     # source B: custom FireRed
    c_list = cry_lists[hid - 1] if hid <= 251 else []    # source C: custom Crystal (Gen 1/2 only)

    seen = set()
    merged = []
    for lvl, mv in a_list + b_list + c_list:
        key = (lvl, mv)
        if key in seen:
            continue
        seen.add(key)
        merged.append(key)
    merged = [x for _, x in sorted(enumerate(merged), key=lambda t: (t[1][0], t[0]))]

    length_hist.append((len(merged), name))
    max_len = max(max_len, len(merged))
    if merged != a_list:
        changed += 1
        if len(examples) < 5:
            examples.append('%s: %d -> %d moves' % (name, len(a_list), len(merged)))
        blob = b''.join(struct.pack('<H', (lv << 9) | mv) for lv, mv in merged) + b'\xff\xff'
        wot.members[hid] = bytearray(blob)

report('LEARNSETS rewritten (3-way union: vanilla HG + custom FireRed + custom Crystal)',
       ['%d changed of 386, longest merged list: %d moves' % (changed, max_len)] + examples, 20)
length_hist.sort(reverse=True)
report('Longest merged lists (top 10)', ['%s: %d moves' % (n, l) for l, n in length_hist[:10]], 10)

if max_len > 40:
    print('\n!! WARNING: longest merged list (%d) EXCEEDS the current 40-entry buffer '
          '(LEARNSET_BUFFER_ENTRIES / RELEARNER_LEARNSET_ENTRIES from ENTRY AE) - '
          'those buffers must be enlarged again before this is safe to ship.' % max_len)

if not APPLY:
    print('\nDRY RUN - nothing written. Re-run with --apply to write files/poketool/personal/wotbl.narc.')
    sys.exit(0)

open(WOTBL, 'wb').write(wot.build())
chk = Narc(WOTBL)
assert chk.count == wot.count
for i in range(chk.count):
    assert bytes(chk.members[i]) == bytes(wot.members[i]), 'wotbl member %d differs after write' % i
print('\nWRITTEN and re-verified: files/poketool/personal/wotbl.narc')
