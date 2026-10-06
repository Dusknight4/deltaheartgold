"""Fills in HeartGold held items from the user's FireRed romhack (pokefirered-master/), but ONLY into slots that
are currently EMPTY (ITEM_NONE) in HeartGold - existing HeartGold items (including ones just copied over from
UltimateCrystal by apply_ultimatecrystal_items.py) are never overwritten. Slot is preserved: FireRed itemCommon ->
HeartGold items[0], itemRare -> items[1].

Run from the repo root:
    python3 tools/apply_firered_items.py            # dry run: prints what WOULD change
    python3 tools/apply_firered_items.py --apply    # writes files/poketool/personal/personal.json

Species matching is by NATIONAL DEX NUMBER (species_info.h is itself indexed by dex number via SPECIES_ defines,
same as HeartGold's personal.json baseStats array), covering species 1-386 (FireRed/LeafGreen's Gen 1-3 dex).

Item name translation: FireRed's constants are Gen 3-era. Two items (Up-Grade, Silver Powder / Twisted Spoon /
Tiny Mushroom / Never-Melt Ice) use an underscore where HeartGold's constant has none; FR_ITEM_TO_HG below maps
those explicitly. Everything else matches directly as the same ITEM_ constant name in both games.
"""
import json, re, sys

APPLY = '--apply' in sys.argv

FR_SPECIES_INFO = 'pokefirered-master/src/data/pokemon/species_info.h'
PERSONAL = 'files/poketool/personal/personal.json'

FR_ITEM_TO_HG = {
    'ITEM_UP_GRADE': 'ITEM_UPGRADE',
    'ITEM_SILVER_POWDER': 'ITEM_SILVERPOWDER',
    'ITEM_TWISTED_SPOON': 'ITEM_TWISTEDSPOON',
    'ITEM_TINY_MUSHROOM': 'ITEM_TINYMUSHROOM',
    'ITEM_NEVER_MELT_ICE': 'ITEM_NEVERMELTICE',
}


def load_hg_item_names():
    names = set()
    for line in open('include/constants/items.h', encoding='utf-8', errors='replace'):
        m = re.match(r'#define\s+(ITEM_[A-Z0-9_]+)\s+\d+\b', line)
        if m:
            names.add(m.group(1))
    return names


def fr_to_hg_item(fr_name, hg_item_names):
    mapped = FR_ITEM_TO_HG.get(fr_name, fr_name)
    if mapped in hg_item_names:
        return mapped
    return False


def parse_fr_items():
    """Returns {dex_number: (itemCommon, itemRare)} for species 1-386."""
    fr_species_ids = {}
    for line in open('pokefirered-master/include/constants/species.h', encoding='utf-8', errors='replace'):
        m = re.match(r'#define\s+SPECIES_([A-Z0-9_]+)\s+(\d+)\b', line)
        if m:
            fr_species_ids[m.group(1)] = int(m.group(2))

    src = open(FR_SPECIES_INFO, encoding='utf-8', errors='replace').read()
    body = src[src.index('const struct SpeciesInfo gSpeciesInfo[]'):]
    out = {}
    for m in re.finditer(r'\[SPECIES_([A-Z0-9_]+)\]\s*=\s*(\{0\}|\{.*?\n    \}),', body, re.S):
        name, blk = m.group(1), m.group(2)
        if blk == '{0}' or name == 'NONE':
            continue
        dex = fr_species_ids.get(name)
        if dex is None or dex < 1 or dex > 386:
            continue
        mc = re.search(r'\.itemCommon\s*=\s*(ITEM_[A-Z0-9_]+)', blk)
        mr = re.search(r'\.itemRare\s*=\s*(ITEM_[A-Z0-9_]+)', blk)
        if mc and mr:
            out[dex] = (mc.group(1), mr.group(1))
    return out


def main():
    hg_item_names = load_hg_item_names()
    fr_data = parse_fr_items()

    raw_json = open(PERSONAL, encoding='utf-8').read()
    pj = json.loads(raw_json)
    assert json.dumps(pj, indent=2, ensure_ascii=False) + '\n' == raw_json or json.dumps(pj, indent=2, ensure_ascii=False) == raw_json, \
        'personal.json does not round-trip through json.dumps(indent=2); refusing to rewrite it'

    changes = []
    unmapped = []
    for dex, (fr_common, fr_rare) in sorted(fr_data.items()):
        hg_entry = pj['baseStats'][dex]
        new_items = list(hg_entry['items'])
        for slot, fr_item in enumerate((fr_common, fr_rare)):
            if fr_item == 'ITEM_NONE':
                continue
            if new_items[slot] != 'ITEM_NONE':
                continue  # HG already has something in this slot - preserve it, do not overwrite
            mapped = fr_to_hg_item(fr_item, hg_item_names)
            if mapped is False:
                unmapped.append('#%03d %-12s slot%d: UNRECOGNIZED FireRed item constant %r (not applied)' %
                                 (dex, hg_entry['species'], slot, fr_item))
                continue
            changes.append('#%03d %-12s slot%d: ITEM_NONE -> %s  (FireRed: %s)' %
                            (dex, hg_entry['species'], slot, mapped, fr_item))
            new_items[slot] = mapped
        if new_items != hg_entry['items'] and APPLY:
            hg_entry['items'] = new_items

    print('\n== ITEMS FILLED (HG slot was empty): %d' % len(changes))
    for c in changes:
        print('   ', c)
    print('\n== NOT APPLIED (unrecognized item constant): %d' % len(unmapped))
    for u in unmapped:
        print('   ', u)

    if not APPLY:
        print('\nDRY RUN - nothing written. Re-run with --apply to write the file.')
        return

    open(PERSONAL, 'w', encoding='utf-8').write(json.dumps(pj, indent=2, ensure_ascii=False) + ('\n' if raw_json.endswith('\n') else ''))
    reread = json.loads(open(PERSONAL, encoding='utf-8').read())
    for dex in fr_data:
        assert reread['baseStats'][dex]['items'] == pj['baseStats'][dex]['items']
    print('\nWRITTEN and re-verified: personal.json')


if __name__ == '__main__':
    main()
