"""Reads Base_Stats.txt (as hand-edited by the project owner) and applies any base-stat / EXP yield changes back
into files/poketool/personal/personal.json. Only base stats (HP/Atk/Def/SpAtk/SpDef/Speed) and EXP Yield are
applied by this script - Type/Held Items/Level-Up Moves/TM-HM Moves in Base_Stats.txt are informational only for
now (not parsed back). Matching is by the "#NNN SPECIES" header, i.e. national dex index, same as personal.json's
own baseStats array indexing.

Run from the repo root:
    python3 tools/apply_base_stats_txt_edits.py            # dry run: prints what WOULD change
    python3 tools/apply_base_stats_txt_edits.py --apply    # writes files/poketool/personal/personal.json
"""
import json, re, sys

APPLY = '--apply' in sys.argv

TXT = 'Base_Stats.txt'
PERSONAL = 'files/poketool/personal/personal.json'

HEADER_RE = re.compile(r'^#(\d+)\s+(\S+)')
STATS_RE = re.compile(r'Base Stats: HP (\d+) / Atk (\d+) / Def (\d+) / SpAtk (\d+) / SpDef (\d+) / Speed (\d+)')
EXPYIELD_RE = re.compile(r'Exp Yield: (\d+)')


def parse_txt(path):
    """Returns {dex: {'species': name, 'hp':.., 'atk':.., ..., 'expYield':..}}"""
    out = {}
    cur_dex = None
    cur_name = None
    for line in open(path, encoding='utf-8', errors='replace'):
        m = HEADER_RE.match(line)
        if m:
            cur_dex = int(m.group(1))
            cur_name = m.group(2)
            continue
        m = STATS_RE.search(line)
        if m and cur_dex is not None:
            out.setdefault(cur_dex, {'species': cur_name})
            out[cur_dex]['hp'] = int(m.group(1))
            out[cur_dex]['atk'] = int(m.group(2))
            out[cur_dex]['def'] = int(m.group(3))
            out[cur_dex]['spatk'] = int(m.group(4))
            out[cur_dex]['spdef'] = int(m.group(5))
            out[cur_dex]['speed'] = int(m.group(6))
            continue
        m = EXPYIELD_RE.search(line)
        if m and cur_dex is not None:
            out.setdefault(cur_dex, {'species': cur_name})
            out[cur_dex]['expYield'] = int(m.group(1))
    return out


def main():
    txt_data = parse_txt(TXT)

    raw_json = open(PERSONAL, encoding='utf-8').read()
    pj = json.loads(raw_json)
    assert json.dumps(pj, indent=2, ensure_ascii=False) + '\n' == raw_json or json.dumps(pj, indent=2, ensure_ascii=False) == raw_json, \
        'personal.json does not round-trip through json.dumps(indent=2); refusing to rewrite it'

    changes = []
    STAT_KEYS = ('hp', 'atk', 'def', 'spatk', 'spdef', 'speed', 'expYield')
    for dex, rec in sorted(txt_data.items()):
        if dex >= len(pj['baseStats']):
            continue
        hg_entry = pj['baseStats'][dex]
        if hg_entry['species'] != rec['species']:
            print('WARNING: #%03d name mismatch: personal.json has %s, Base_Stats.txt has %s - skipped' %
                  (dex, hg_entry['species'], rec['species']))
            continue
        for k in STAT_KEYS:
            if k not in rec:
                continue
            if hg_entry[k] != rec[k]:
                changes.append('#%03d %-12s %-8s %d -> %d' % (dex, rec['species'], k, hg_entry[k], rec[k]))
                if APPLY:
                    hg_entry[k] = rec[k]

    print('\n== STAT/EXP CHANGES: %d' % len(changes))
    for c in changes:
        print('   ', c)

    if not APPLY:
        print('\nDRY RUN - nothing written. Re-run with --apply to write the file.')
        return

    open(PERSONAL, 'w', encoding='utf-8').write(json.dumps(pj, indent=2, ensure_ascii=False) + ('\n' if raw_json.endswith('\n') else ''))
    reread = json.loads(open(PERSONAL, encoding='utf-8').read())
    for dex in txt_data:
        if dex < len(pj['baseStats']):
            assert reread['baseStats'][dex] == pj['baseStats'][dex]
    print('\nWRITTEN and re-verified: personal.json')


if __name__ == '__main__':
    main()
