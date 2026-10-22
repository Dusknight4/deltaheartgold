#!/usr/bin/env python3
"""ENTRY DY: make an nds-bootstrap copy of a HeartGold build by changing ONLY the header game code (IPKE -> IPKX).

nds-bootstrap v2.x applies its built-in anti-piracy fix (nitro:/apfix.pck) by game code alone; for IPKE it writes
"bl 0x02000228" at 0x020D8C1C, which lands inside FSi_SendCommand in this mod (Data Abort at 0x0200022C on the DS Lite).
With game code IPKX there is no entry, so nds-bootstrap patches nothing there, and the code stays byte-identical to the
build it was made from. YSMenu has no IPKX entry either, but YSMenu picks the save type by game code too - keep using the
normal IPKE build on YSMenu.

The game code is part of the header, so the header CRC (0x15E) is recomputed.

usage: make_ndsb_copy.py <in.nds> <out.nds> [GAMECODE]   (default IPKX)
"""
import shutil
import struct
import sys


def crc16(data):
    crc = 0xFFFF
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def main():
    if len(sys.argv) not in (3, 4):
        sys.exit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    code = (sys.argv[3] if len(sys.argv) == 4 else 'IPKX').encode()
    if len(code) != 4:
        sys.exit('game code must be 4 characters')
    shutil.copyfile(src, dst)
    with open(dst, 'r+b') as f:
        hdr = bytearray(f.read(0x200))
        if crc16(hdr[:0x15E]) != struct.unpack_from('<H', hdr, 0x15E)[0]:
            sys.exit('%s: header CRC is not valid - not a finished ROM?' % src)
        old = bytes(hdr[0x0C:0x10])
        hdr[0x0C:0x10] = code
        struct.pack_into('<H', hdr, 0x15E, crc16(hdr[:0x15E]))
        f.seek(0)
        f.write(hdr)
    print('%s: game code %s -> %s, header CRC 0x%04X' % (dst, old.decode(errors='replace'), code.decode(), crc16(hdr[:0x15E])))


if __name__ == '__main__':
    main()
