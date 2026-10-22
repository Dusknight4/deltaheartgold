// ysmguard - ENTRY DV (R4 / YSMenu compatibility), ENTRY DX (modern nds-bootstrap).
//
// YSMenu (the R4 / DSTT menu) recognises the game code IPKE and, right after the ARM9 image is decompressed, writes its
// anti-piracy fix for the ORIGINAL HeartGold to fixed addresses (TTMenu/extinfo.dat). In this modified game other code lives
// at those addresses, so the game hangs on a white screen. src/main.c holds a table of those places (gYSMenuGuard); this tool
// runs on the linked, still uncompressed static image (build/<rom>/main.sbin, loaded at 0x02000000) before compstatic and
// copies the original bytes of every place into the table, so the game can put them back when it finds YSMenu's patch.
// ENTRY DX: modern nds-bootstrap (v2.x) patches 0x020D8C1C for IPKE; its table is gNdsBootstrapGuard in src/loader_guard.c
// (same format, own magic). Every table listed in kGuards is filled.
//
// usage: ysmguard main.sbin
// Fails (exit 1) if a table is missing or malformed, so a ROM without filled tables is never built.

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define ARM9_LOAD_ADDR   0x02000000u
#define NITRO_FOOTER_LEN 12
#define GUARD_MAGIC_LEN  16 // magic string + NUL padding
#define MAX_SITES        8
#define SITE_LEN         24 // u32 addr, u32 size, u8 patch[8], u8 orig[8]

static const struct {
    char magic[GUARD_MAGIC_LEN];
    const char *where;
} kGuards[] = {
    { "YSMENU_GUARD_V1", "gYSMenuGuard, src/main.c" },
    { "NDSB_GUARD_V1", "gNdsBootstrapGuard, src/loader_guard.c" },
};

static uint32_t rd32(const uint8_t *p) {
    return p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24);
}

static void wr32(uint8_t *p, uint32_t v) {
    p[0] = v & 0xFF;
    p[1] = (v >> 8) & 0xFF;
    p[2] = (v >> 16) & 0xFF;
    p[3] = (v >> 24) & 0xFF;
}

// Finds one table and copies the build's own bytes into it. Returns 0 on success.
static int FillGuard(uint8_t *data, long size, const char *magic, const char *where) {
    long i, guardOff = -1;
    uint32_t numSites, s;

    for (i = 0; i + GUARD_MAGIC_LEN <= size; i += 4) {
        if (memcmp(data + i, magic, GUARD_MAGIC_LEN) == 0) {
            if (guardOff != -1) {
                fprintf(stderr, "ysmguard: the table magic %s appears twice\n", magic);
                return 1;
            }
            guardOff = i;
        }
    }
    if (guardOff == -1) {
        fprintf(stderr, "ysmguard: guard table %s (%s) not found\n", magic, where);
        return 1;
    }

    numSites = rd32(data + guardOff + GUARD_MAGIC_LEN);
    if (numSites == 0 || numSites > MAX_SITES || guardOff + GUARD_MAGIC_LEN + 8 + numSites * SITE_LEN > (uint32_t)size) {
        fprintf(stderr, "ysmguard: %s: bad site count %u\n", magic, numSites);
        return 1;
    }

    for (s = 0; s < numSites; s++) {
        uint8_t *site = data + guardOff + GUARD_MAGIC_LEN + 8 + s * SITE_LEN;
        uint32_t addr = rd32(site);
        uint32_t len = rd32(site + 4);
        long off = (long)addr - (long)ARM9_LOAD_ADDR;
        long guardStart = guardOff, guardEnd = guardOff + GUARD_MAGIC_LEN + 8 + numSites * SITE_LEN;

        if (len == 0 || len > 8 || off < 0 || off + (long)len > size - NITRO_FOOTER_LEN) {
            fprintf(stderr, "ysmguard: %s site %u (0x%08X, %u bytes) is outside the static image\n", magic, s, addr, len);
            return 1;
        }
        if (off < guardEnd && off + (long)len > guardStart) {
            fprintf(stderr, "ysmguard: %s site %u (0x%08X) overlaps the guard table itself\n", magic, s, addr);
            return 1;
        }
        memcpy(site + 16, data + off, len);
        printf("ysmguard: %s 0x%08X:", magic, addr);
        for (i = 0; i < (long)len; i++) {
            printf(" %02X", site[16 + i]);
        }
        printf("%s\n", memcmp(site + 8, site + 16, len) == 0 ? "  (same as the loader's patch - nothing to restore)" : "");
    }

    wr32(data + guardOff + GUARD_MAGIC_LEN + 4, 1); // filled
    return 0;
}

int main(int argc, char **argv) {
    FILE *f;
    uint8_t *data;
    long size;
    size_t g;

    if (argc != 2) {
        fprintf(stderr, "usage: ysmguard main.sbin\n");
        return 1;
    }

    f = fopen(argv[1], "rb");
    if (f == NULL) {
        fprintf(stderr, "ysmguard: cannot open %s\n", argv[1]);
        return 1;
    }
    fseek(f, 0, SEEK_END);
    size = ftell(f);
    fseek(f, 0, SEEK_SET);
    data = malloc(size);
    if (data == NULL || fread(data, 1, size, f) != (size_t)size) {
        fprintf(stderr, "ysmguard: cannot read %s\n", argv[1]);
        return 1;
    }
    fclose(f);

    for (g = 0; g < sizeof(kGuards) / sizeof(kGuards[0]); g++) {
        if (FillGuard(data, size, kGuards[g].magic, kGuards[g].where) != 0) {
            return 1;
        }
    }

    f = fopen(argv[1], "r+b");
    if (f == NULL || fwrite(data, 1, size, f) != (size_t)size) {
        fprintf(stderr, "ysmguard: cannot write %s\n", argv[1]);
        return 1;
    }
    fclose(f);
    free(data);
    return 0;
}
