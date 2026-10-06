"""Generates include/species_abilities_table.h from files/poketool/personal/personal.narc.

Each personal entry (BASE_STATS) holds the two abilities at byte offsets 0x16 and 0x17. The ability-donor code looks abilities up
from this static table instead of calling GetMonBaseStat, because GetMonBaseStat allocates memory and reads the ROM on every call.
Run from the repo root:  python3 tools/gen_species_abilities.py
"""
import struct, sys

NATIONAL_DEX_COUNT = 493

b = open('files/poketool/personal/personal.narc', 'rb').read()
btaf = 0x10
count = struct.unpack_from('<H', b, btaf + 8)[0]
btnf = btaf + struct.unpack_from('<I', b, btaf + 4)[0]
gmif = btnf + struct.unpack_from('<I', b, btnf + 4)[0]
data = gmif + 8

def member(i):
    s, e = struct.unpack_from('<II', b, btaf + 0xC + i * 8)
    return b[data + s:data + e]

rows = []
for sp in range(NATIONAL_DEX_COUNT + 1):
    m = member(sp)
    rows.append((m[0x16], m[0x17]))

# sanity checks against well known species (HGSS ability ids)
assert rows[1][0] == 65, rows[1]                           # Bulbasaur: Overgrow (65)
assert rows[25][0] == 9, rows[25]                            # Pikachu: Static
assert rows[158][0] == 67, rows[158]                         # Totodile: Torrent (67)
print('personal members: %d; species table rows: %d' % (count, len(rows)), file=sys.stderr)
for sp in (1, 25, 158, 160, 493):
    print('  species %3d abilities %s' % (sp, rows[sp]), file=sys.stderr)

out = []
out.append('// GENERATED FILE - do not edit by hand. Regenerate with: python3 tools/gen_species_abilities.py')
out.append('//')
out.append('// The two abilities of every national dex species (index 0 is unused), copied from the game\'s personal data')
out.append('// (files/poketool/personal/personal.narc, BASE_STATS.abilities). Used by the ability-donor code so it does not have to')
out.append('// call GetMonBaseStat (which allocates memory and reads the ROM on every call).')
out.append('#ifndef POKEHEARTGOLD_SPECIES_ABILITIES_TABLE_H')
out.append('#define POKEHEARTGOLD_SPECIES_ABILITIES_TABLE_H')
out.append('')
out.append('#define SPECIES_ABILITIES_TABLE_COUNT %d' % (NATIONAL_DEX_COUNT + 1))
out.append('')
out.append('static const u8 sSpeciesAbilities[SPECIES_ABILITIES_TABLE_COUNT][2] = {')
line = []
for sp, (a, c) in enumerate(rows):
    line.append('{ %d, %d }' % (a, c))
    if len(line) == 8:
        out.append('    ' + ', '.join(line) + ',')
        line = []
if line:
    out.append('    ' + ', '.join(line) + ',')
out.append('};')
out.append('')
out.append('#endif // POKEHEARTGOLD_SPECIES_ABILITIES_TABLE_H')
open('include/species_abilities_table.h', 'w').write('\n'.join(out) + '\n')
print('wrote include/species_abilities_table.h', file=sys.stderr)
