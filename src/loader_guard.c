// ---------------------------------------------------------------------------------------------------------------------
// ENTRY DW / DX: MODERN NDS-BOOTSTRAP COMPATIBILITY.
// nds-bootstrap v2.x carries its own anti-piracy fix pack (nitro:/apfix.pck). Its IPKE entry matches any checksum and,
// before the game starts, writes "bl 0x02000228" at 0x020D8C1C plus 56 bytes of hook code over unused secure-area filler
// at 0x02000228. In the original game 0x020D8C1C is the anti-piracy spot; in this mod it is inside FSi_SendCommand, so the
// first file read jumped into the hook -> "Data Abort!" at PC 0x0200022C on the DS Lite. tools/ysmguard copies this
// build's own bytes into the table below after linking; LoaderGuard_StartUp() puts them back when nds-bootstrap's call is
// there. The 56 hook bytes stay but are never called.
//
// Why a separate file, run from crt0 instead of NitroMain (ENTRY DX): R4FIX-v2's code layout is the one confirmed on the
// owner's R4 (YSMenu, guard in src/main.c). Adding this code to main.c moved every function after it (ENTRY DW,
// NDSBFIX-v1, white screen on the owner's DS Lite with both YSMenu and nds-bootstrap). This file is linked LAST in the
// static module (main.lsf) and crt0 calls it in place of its empty NitroStartUp stub (same instruction, same size), so
// every function of the static module stays at its R4FIX-v2 address. ARM code: crt0 calls it with a plain ARM "bl".
// ---------------------------------------------------------------------------------------------------------------------
#include "global.h"

#include <nitro/code32.h>

typedef struct LoaderGuardSite {
    u32 addr;
    u32 size;
    u8 patch[8]; // what the loader writes there
    u8 orig[8]; // this build's own bytes (filled in by tools/ysmguard)
} LoaderGuardSite;

typedef struct LoaderGuard {
    char magic[16]; // located by tools/ysmguard
    u32 numSites;
    u32 filled; // 1 once tools/ysmguard has filled in orig[]
    LoaderGuardSite sites[1];
} LoaderGuard;

void LoaderGuard_StartUp(void); // called from lib/asm/crt0.s

LoaderGuard gNdsBootstrapGuard = {
    "NDSB_GUARD_V1",
    1,
    0,
    {
        { 0x020D8C1C, 4, { 0x81, 0x9D, 0xFC, 0xEB } }, // bl 0x02000228
    },
};

void LoaderGuard_StartUp(void) {
    volatile LoaderGuard *guard = &gNdsBootstrapGuard;
    u32 i, j;

    if (guard->filled != 1) {
        return;
    }
    for (i = 0; i < guard->numSites; i++) {
        volatile LoaderGuardSite *site = &guard->sites[i];
        vu8 *code = (vu8 *)site->addr;

        for (j = 0; j < site->size; j++) {
            if (code[j] != site->patch[j]) {
                break;
            }
        }
        if (j != site->size) {
            continue;
        }
        for (j = 0; j < site->size; j++) {
            code[j] = site->orig[j];
        }
        DC_FlushRange((void *)site->addr, site->size);
        IC_InvalidateRange((void *)site->addr, site->size);
    }
}

#include <nitro/codereset.h>
