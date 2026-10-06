"""Generates include/species_gender_ratios_table.h from files/poketool/personal/personal.narc.

Each personal entry (BASE_STATS) holds its gender ratio at byte offset 0x10 (include/pokemon_types_def.h's
BaseStats.genderRatio - confirmed against the same struct's abilities[2] at 0x16/0x17, which
tools/gen_species_abilities.py already uses directly as raw offsets 0x16/0x17, so the struct's declared
layout is a direct, unpadded match for the on-disk member bytes here too).

WHY THIS EXISTS (ENTRY L / ENTRY AC precedent): computing a mon's gender via GetMonGender ->
GetBoxMonGender -> GetGenderBySpeciesAndPersonality calls AllocAndLoadMonPersonal(species, HEAP_ID_DEFAULT)
internally, which allocates memory AND reads the ROM filesystem on every single call - ENTRY L already
diagnosed this exact pattern (in a different follow_mon.c function) as the cause of "black screen leaving
the Pokemon Center" and long stalls, when called from a hot path. ENTRY AC's ability-donor code already
established the fix pattern for abilities (a pre-generated static table instead of a ROM read on every
call) - this does the same thing for gender ratio, so FollowMon_ChangeMon (src/follow_mon.c, called every
time the field is restored after returning from battle - the exact kind of hot, resource-contended moment
ENTRY L warned about) can compute a mon's gender without touching the heap or the ROM at all.

Run from the repo root:  python3 tools/gen_species_gender_ratios.py
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
    rows.append(m[0x10])

# sanity checks against well known species (HGSS gender ratios: 0=all male, 254=all female, 255=genderless,
# other values are a male/female split threshold out of 255 - see MON_RATIO_MALE/FEMALE/UNKNOWN in
# include/constants/pokemon.h and GetGenderBySpeciesAndPersonality_PreloadedPersonal in src/pokemon.c).
# Printed (not hard-asserted) first to verify against real data instead of trusting recalled values blind -
# a first attempt asserted Pikachu was in the 87.5%-male starter group (like Bulbasaur/Totodile) and was
# wrong (real data: 127, 50/50) - fixed below to check known-fixed-point cases only (100% male / genderless).
print('personal members: %d; species table rows: %d' % (count, len(rows)), file=sys.stderr)
for sp in (1, 25, 133, 158, 292, 493):
    print('  species %3d genderRatio %3d' % (sp, rows[sp]), file=sys.stderr)
assert rows[292] == 255, rows[292]  # Shedinja: genderless (only has one gender-ratio value possible)
assert rows[128] == 0, rows[128]    # Tauros: 100% male (only has one gender-ratio value possible)

out = []
out.append('// GENERATED FILE - do not edit by hand. Regenerate with: python3 tools/gen_species_gender_ratios.py')
out.append('//')
out.append('// The gender ratio of every national dex species (index 0 is unused), copied from the game\'s personal')
out.append('// data (files/poketool/personal/personal.narc, BaseStats.genderRatio, offset 0x10). Used by follow_mon.c')
out.append('// so it does not have to call GetMonGender / AllocAndLoadMonPersonal, which allocates memory and reads')
out.append('// the ROM on every call (ENTRY L already hit and fixed this exact trap once, in a different function).')
out.append('#ifndef POKEHEARTGOLD_SPECIES_GENDER_RATIOS_TABLE_H')
out.append('#define POKEHEARTGOLD_SPECIES_GENDER_RATIOS_TABLE_H')
out.append('')
out.append('#define SPECIES_GENDER_RATIOS_TABLE_COUNT %d' % (NATIONAL_DEX_COUNT + 1))
out.append('')
out.append('static const u8 sSpeciesGenderRatios[SPECIES_GENDER_RATIOS_TABLE_COUNT] = {')
line = []
for sp, ratio in enumerate(rows):
    line.append('%d' % ratio)
    if len(line) == 16:
        out.append('    ' + ', '.join(line) + ',')
        line = []
if line:
    out.append('    ' + ', '.join(line) + ',')
out.append('};')
out.append('')
out.append('#endif // POKEHEARTGOLD_SPECIES_GENDER_RATIOS_TABLE_H')
open('include/species_gender_ratios_table.h', 'w').write('\n'.join(out) + '\n')
print('wrote include/species_gender_ratios_table.h', file=sys.stderr)
