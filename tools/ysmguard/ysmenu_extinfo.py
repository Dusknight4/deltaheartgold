#!/usr/bin/env python3
"""ENTRY DU/DV diagnostic: show what YSMenu (R4 / DSTT menu) writes into a game before starting it, and what a ROM has there.

YSMenu's TTMenu/extinfo.dat holds per-game-code patches, every byte stored inverted (XOR 0xFF):
    0x00  "ExtInfo\\0", u32 version, u32 count, 16 x 0xFF
    0x20  count x { ~gamecode[4], ~u32 crc }          (crc 0 = any checksum)
    then  count x { ~u32 offset, ~u32 size }           (where each entry's data is in the file)
    entry data (inverted): u32 numRecords, then numRecords x { u32 address, u32 size, u8 bytes[size] }
YSMenu writes every record to its address in RAM before the game runs (for a compressed ARM9: right after the
game's crt0 has decompressed it), whatever code is there.

usage: ysmenu_extinfo.py <extinfo.dat> <GAMECODE> [rom.nds ...]
example: ysmenu_extinfo.py "<card>/TTMenu/extinfo.dat" IPKE test_roms/pokeheartgold_R4FIX-v2.nds
"""
import struct
import sys


def inv(b):
    return bytes(x ^ 0xFF for x in b)


def read_entry(extinfo, code):
    d = open(extinfo, 'rb').read()
    if d[:7] != b'ExtInfo':
        sys.exit('not an extinfo.dat')
    n = struct.unpack_from('<I', d, 12)[0]
    table = 0x20 + n * 8
    for i in range(n):
        if inv(d[0x20 + i * 8:0x24 + i * 8]) == code:
            crc = struct.unpack('<I', inv(d[0x24 + i * 8:0x28 + i * 8]))[0]
            off, size = struct.unpack('<2I', inv(d[table + i * 8:table + i * 8 + 8]))
            data = inv(d[off:off + size])
            records, p = [], 4
            for _ in range(struct.unpack_from('<I', data, 0)[0]):
                addr, length = struct.unpack_from('<2I', data, p)
                records.append((addr, data[p + 8:p + 8 + length]))
                p += 8 + length
            return crc, records
    return None, []


def blz_decompress(arm9, load, comp_end):
    """Nintendo backward LZ (MIi_UncompressBackward) of the ARM9 static image as it sits in RAM at 'load'."""
    c = comp_end - load
    top_bottom, extra = struct.unpack_from('<2I', arm9, c - 8)
    out = bytearray(arm9[:c]) + bytearray(extra)
    src, dst, stop = c - (top_bottom >> 24), c + extra, c - (top_bottom & 0xFFFFFF)
    while src > stop:
        flags = out[src - 1]
        src -= 1
        for _ in range(8):
            if src <= stop:
                break
            if flags & 0x80:
                val = (out[src - 1] << 8) | out[src - 2]
                src -= 2
                disp, length = (val & 0xFFF) + 3, (val >> 12) + 3
                for _ in range(length):
                    dst -= 1
                    out[dst] = out[dst + disp]
            else:
                dst -= 1
                src -= 1
                out[dst] = out[src]
            flags = (flags << 1) & 0xFF
    return bytes(out)


def arm9_ram(rom):
    with open(rom, 'rb') as f:
        hdr = f.read(0x200)
        off, _, load, size = struct.unpack_from('<4I', hdr, 0x20)
        f.seek(off)
        arm9 = f.read(size)
        _, params, _ = struct.unpack('<3I', f.read(12))
    comp_end = struct.unpack_from('<I', arm9, params + 20)[0]
    return load, (blz_decompress(arm9, load, comp_end) if comp_end else arm9), hdr[0x0C:0x10]


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    code = sys.argv[2].encode()
    crc, records = read_entry(sys.argv[1], code)
    if crc is None:
        print('%s: no entry - YSMenu patches nothing for this game code' % code.decode())
        return
    print('%s: %d record(s), checksum %s' % (code.decode(), len(records), 'any' if crc == 0 else '0x%08X' % crc))
    for addr, data in records:
        print('   0x%08X  %3d bytes  %s' % (addr, len(data), data[:16].hex(' ') + (' ...' if len(data) > 16 else '')))
    for rom in sys.argv[3:]:
        load, ram, rom_code = arm9_ram(rom)
        print('== %s (game code %s)' % (rom, rom_code.decode(errors='replace')))
        for addr, data in records:
            o = addr - load
            if 0 <= o < len(ram):
                print('   0x%08X: ROM has %-24s YSMenu writes %s' % (addr, ram[o:o + min(len(data), 8)].hex(' '), data[:8].hex(' ')))
            else:
                print('   0x%08X: outside the ARM9 static image (YSMenu\'s own code - harmless)' % addr)


if __name__ == '__main__':
    main()
