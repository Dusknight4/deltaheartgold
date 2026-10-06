"""Copies held items from the user's UltimateCrystal romhack (Gen 1/2, species #1-251) into HeartGold's
files/poketool/personal/personal.json, preserving item slot (UC item1 -> HG items[0], UC item2 -> HG items[1]).
This is a DIRECT COPY (overwrites whatever HG currently has in that slot) - UltimateCrystal is the source of truth
here, per the project owner (it was edited first and already has custom Gen 1/2 held items, e.g. Scizor holding
Metal Coat in both slots).

Run from the repo root:
    python3 tools/apply_ultimatecrystal_items.py            # dry run: prints what WOULD change
    python3 tools/apply_ultimatecrystal_items.py --apply    # writes files/poketool/personal/personal.json

Species matching is by NATIONAL DEX NUMBER (from the "; NNN" comment on each UltimateCrystal base_stats/*.asm
file's species line), not by name - UltimateCrystal (Gen 2 disassembly) and HeartGold (Gen 4 decomp) use different
constant-naming conventions for a few species (e.g. MR__MIME vs MR_MIME, FARFETCH_D vs FARFETCHD), so index-matching
by dex number sidesteps all of that safely. HeartGold's personal.json baseStats array is itself indexed by dex
number, so species 1-251 there are exactly UltimateCrystal's coverage (Gen 1 and Gen 2).

Item name translation: UltimateCrystal's constants are Gen 2-era (no "ITEM_" prefix, and some items were renamed or
removed by Gen 4). UC_ITEM_TO_HG below is the explicit translation table, using the well-documented Gen 2 -> Gen 3+
item renames (matches the historical Pal Park / Poke Transporter conversion table) for anything that changed name;
two Gen 2 items were removed entirely by Gen 4 and have NO HeartGold equivalent (Berserk Gene, and "Gold Leaf" -
Magikarp's item, which is not a real Pokemon item name at all and this romhack's own custom invention) - species
using either are reported and their affected slot is left UNCHANGED, never guessed.
"""
import json, re, sys, glob

APPLY = '--apply' in sys.argv

UC_DIR = 'UltimateCrystal-master/data/pokemon/base_stats'
PERSONAL = 'files/poketool/personal/personal.json'

# UltimateCrystal (Gen 2) item constant -> HeartGold (Gen 4) item constant.
# Items whose Gen 2 name is unchanged in Gen 4 are not listed here; they are matched automatically as
# UC name -> 'ITEM_' + UC name (verified against include/constants/items.h before running).
UC_ITEM_TO_HG = {
    'NO_ITEM': 'ITEM_NONE',
    'BERRY': 'ITEM_ORAN_BERRY',           # Gen 2 "Berry" (cures poison, weak heal) -> Oran Berry
    'GOLD_BERRY': 'ITEM_SITRUS_BERRY',    # Gen 2 "Gold Berry" (stronger heal) -> Sitrus Berry
    'MYSTERYBERRY': 'ITEM_LEPPA_BERRY',   # restores 10 PP to one move -> Leppa Berry (same effect)
    'MIRACLEBERRY': 'ITEM_LUM_BERRY',     # cures any status -> Lum Berry (same effect)
    'BURNT_BERRY': 'ITEM_ASPEAR_BERRY',   # Gen 2 cures FREEZE (yes, backwards name) -> Aspear Berry (cures freeze)
    'ICE_BERRY': 'ITEM_RAWST_BERRY',      # Gen 2 cures BURN (yes, backwards name) -> Rawst Berry (cures burn)
    'BLACKBELT_I': 'ITEM_BLACK_BELT',     # "_I" suffix avoids a name clash in Crystal's own asm; same item
    'POLKADOT_BOW': 'ITEM_SILK_SCARF',    # Polkadot/Pink Bow (Normal-boost) was removed after Gen 3; closest
                                           # accepted functional successor kept into Gen 4 is Silk Scarf (also
                                           # Normal-boost). Not a strict rename like the others - flagged in report.
    'UP_GRADE': 'ITEM_UPGRADE',           # HeartGold's constant has no underscore
    # No HeartGold equivalent - left UNCHANGED, reported instead of guessed:
    'GOLD_LEAF': None,     # not a real Pokemon item in any official game; UltimateCrystal's own invention (Magikarp)
    'BERSERK_GENE': None,  # real Gen 2 item, removed from the series after Gen 2/3 (Mewtwo, Unown)
}


def load_hg_item_names():
    names = set()
    for line in open('include/constants/items.h', encoding='utf-8', errors='replace'):
        m = re.match(r'#define\s+(ITEM_[A-Z0-9_]+)\s+\d+\b', line)
        if m:
            names.add(m.group(1))
    return names


def uc_to_hg_item(uc_name, hg_item_names):
    if uc_name in UC_ITEM_TO_HG:
        return UC_ITEM_TO_HG[uc_name]  # may be None (no equivalent)
    guess = 'ITEM_' + uc_name
    if guess in hg_item_names:
        return guess
    return False  # unrecognized entirely - should not happen; treated as an error, not silently skipped


def parse_uc_base_stats():
    """Returns {dex_number: (species_name, item1, item2)}."""
    out = {}
    for path in glob.glob(UC_DIR + '/*.asm'):
        text = open(path, encoding='utf-8', errors='replace').read()
        m_species = re.search(r'db\s+([A-Z0-9_]+)\s*;\s*(\d+)\s*\n', text)
        m_items = re.search(r'db\s+([A-Z0-9_]+),\s*([A-Z0-9_]+)\s*;\s*items', text)
        if not m_species or not m_items:
            print('WARNING: could not parse %s (species=%s items=%s)' % (path, bool(m_species), bool(m_items)))
            continue
        dex = int(m_species.group(2))
        out[dex] = (m_species.group(1), m_items.group(1), m_items.group(2))
    return out


def main():
    hg_item_names = load_hg_item_names()
    uc_data = parse_uc_base_stats()
    assert len(uc_data) == 251, 'expected 251 UltimateCrystal species, parsed %d' % len(uc_data)

    raw_json = open(PERSONAL, encoding='utf-8').read()
    pj = json.loads(raw_json)
    assert json.dumps(pj, indent=2, ensure_ascii=False) + '\n' == raw_json or json.dumps(pj, indent=2, ensure_ascii=False) == raw_json, \
        'personal.json does not round-trip through json.dumps(indent=2); refusing to rewrite it'

    changes = []
    unmapped = []
    for dex in range(1, 252):
        uc_name, uc_item1, uc_item2 = uc_data[dex]
        hg_entry = pj['baseStats'][dex]
        new_items = list(hg_entry['items'])
        for slot, uc_item in enumerate((uc_item1, uc_item2)):
            mapped = uc_to_hg_item(uc_item, hg_item_names)
            if mapped is False:
                unmapped.append('#%03d %-12s slot%d: UNRECOGNIZED UltimateCrystal item constant %r (not applied)' %
                                 (dex, hg_entry['species'], slot, uc_item))
                continue
            if mapped is None:
                if uc_item != 'NO_ITEM':
                    unmapped.append('#%03d %-12s slot%d: UltimateCrystal has %s, which has NO HeartGold equivalent - left unchanged (was %s)' %
                                     (dex, hg_entry['species'], slot, uc_item, hg_entry['items'][slot]))
                continue
            if new_items[slot] != mapped:
                changes.append('#%03d %-12s slot%d: %s -> %s  (UltimateCrystal: %s)' %
                                (dex, hg_entry['species'], slot, hg_entry['items'][slot], mapped, uc_item))
                new_items[slot] = mapped
        if new_items != hg_entry['items']:
            if APPLY:
                hg_entry['items'] = new_items

    print('\n== ITEM CHANGES: %d' % len(changes))
    for c in changes:
        print('   ', c)
    print('\n== NOT APPLIED (no HeartGold equivalent / unrecognized): %d' % len(unmapped))
    for u in unmapped:
        print('   ', u)

    if not APPLY:
        print('\nDRY RUN - nothing written. Re-run with --apply to write the file.')
        return

    open(PERSONAL, 'w', encoding='utf-8').write(json.dumps(pj, indent=2, ensure_ascii=False) + ('\n' if raw_json.endswith('\n') else ''))
    # verify
    reread = json.loads(open(PERSONAL, encoding='utf-8').read())
    for dex in range(1, 252):
        assert reread['baseStats'][dex]['items'] == pj['baseStats'][dex]['items']
    print('\nWRITTEN and re-verified: personal.json')


if __name__ == '__main__':
    main()
