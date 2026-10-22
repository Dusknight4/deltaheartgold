R4 / YSMENU + NDS-BOOTSTRAP GUARD  (HeartGold ENTRY DU + DV + DW, Platinum ENTRY P110, 2026-10-16)
=================================================================================================

THE PROBLEM
  After NoDSProt-v1 (10-05) every HeartGold build white-screened on the owner's R4 card (DS Lite, YSMenu 7.06),
  while the same ROMs ran in every emulator and on the 3DS (TWiLight Menu++ / nds-bootstrap, DSi mode).
  Earlier builds had done the same on and off since September ("endless white screen", ENTRY AO note).

THE CAUSE
  YSMenu keeps a database of anti-piracy fixes for retail games: TTMenu/extinfo.dat (every byte inverted;
  ysmenu_extinfo.py here decodes it). The entry is chosen by GAME CODE ONLY (checksum "any"). For IPKE it
  writes, before the game runs:
      0x023FC400  236 bytes   YSMenu's own hook code (above the game's RAM - harmless)
      0x0201A570    4 bytes   C0 46 02 E0                (Thumb "nop; skip")
      0x020D8C14    8 bytes   04 F0 1F E5 90 C4 3F 02    (ldr pc, =0x023FC490 - a jump into its hook)
      0x020D8C4C    4 bytes   EB 8D 0C EA                (a branch)
  For CPUE (Platinum) it writes C0 46 02 E0 at 0x02017C28.
  These addresses are anti-piracy spots in the ORIGINAL games. In this mod the code at those addresses is
  something else, and it moves every time code is added - so YSMenu overwrites random game code:
      AIKNOW-v0    jump lands in FSi_SendCommand (every file read)  -> white screen at boot
      LegendBreed  jump lands in FS_SuspendArchive (save access)    -> hangs on hardware
      NoDSProt-v1  jump lands in a branch of FSi_FindPath never hit -> worked, by luck
  The owner's 3DS (nds-bootstrap v1.5.4) is not affected: that version only uses TWiLight's anti-piracy fixes, matched
  by game code AND checksum, and every build of this mod has its own checksum. Emulators apply nothing at all.
  MODERN nds-bootstrap (v2.x) IS affected - see "MODERN NDS-BOOTSTRAP" below (ENTRY DW).

WHY IT TOOK A WHILE (what was ruled out, with evidence - do not retry these)
  * Anti-piracy code coming back: the DSProt removal (ENTRY DN) was intact in every later build.
  * ROM header / layout: identical apart from sizes and offsets.
  * Running out of RAM (startup RAM end crossing 0x023C3000): a build with 8 KB less startup RAM still failed.
  * Game-code-only tests: a copy with Platinum's code CPUE also failed - because YSMenu has a CPUE entry too.
  * Dirty RAM (emulator RAM filled with 0xFF / random before boot): both builds booted.
  * nds-bootstrap v1.5.4 flashcart mode (B4DS) in melonDS: both builds booted (v2.x is different - see below).
  The breakthrough: YSMENU.ARP on the card (a TT Action Replay file) pointed at YSMenu's data files, and the
  inverted-byte format of extinfo.dat decoded into the four records above.

HOW IT WAS PROVEN (reproduce it yourself)
  melonDS (pokeplatinum-main\tools\emu_debug, WideMelon) with [Instance0.Gdb.ARM9] BreakOnStartup = true, then GDB:
      set remote X-packet off                 (melonDS ignores GDB's binary 'X' writes - use 'M' packets)
      target remote 127.0.0.1:3333
      break *0x020008a4                       (HG crt0: right after MIi_UncompressBackward, the ARM9 is unpacked)
      continue
      restore rec0.bin binary 0x023FC400      (the four records, extracted with ysmenu_extinfo.py)
      restore rec1.bin binary 0x0201A570
      restore rec2.bin binary 0x020D8C14
      restore rec3.bin binary 0x020D8C4C
      detach
  AIKNOW-v0 -> white screen exactly like the R4; NoDSProt-v1 -> boots. For Platinum (ARM9 not compressed)
  write C0 46 02 E0 at 0x02017C28 at the first instruction (0x02000800) instead.

THE FIX (keeps the game codes IPKE / CPUE - saves, emulators and the 3DS see no difference)
  1. A table in the game (gYSMenuGuard in src/main.c of each game): magic "YSMENU_GUARD_V1", the places,
     YSMenu's bytes, and the build's own bytes.
  2. The build fills in the build's own bytes automatically:
       HeartGold: tools/ysmguard/ysmguard.c (this folder) runs on build/heartgold.us/main.sbin right before
                  compstatic (Makefile, $(SBIN_LZ) rule; built as a native tool from common.mk NATIVE_TOOLS).
       Platinum:  pokeplatinum-main/tools/debug/ysmguard.py wraps the nitrorom command in meson.build and fills
                  the table in the packed ROM (Platinum's ARM9 image is stored uncompressed).
     Both fail the build if the table is missing or malformed, so an unprotected ROM cannot be produced.
  3. The first thing NitroMain does is YSMenuGuard_UndoPatch(): if YSMenu's bytes are there (HG: the 8-byte jump,
     which nothing else ever writes; Platinum: the 4 bytes, when they differ from the build's own), the build's own
     bytes are written back and the CPU caches are cleaned (DC_FlushRange + IC_InvalidateRange) - before the file
     system, interrupts or InitSystem run. Without YSMenu the function changes nothing.
  Why not change the game code instead: YSMenu would then skip the patch, but other loaders and emulators look up
  save type and per-game settings by game code, so saves and the 3DS setup could break. Undoing the patch has no
  side effects anywhere else.

MAINTENANCE
  * Nothing to do when code is added or moved: the bytes are recorded fresh on every build.
  * Only YSMenu 7.06's extinfo.dat (the last YSMenu) is handled. Other R4 menus (Wood R4, AKAIO, ...) have their
    own patch lists; check them with the same method if someone reports a white screen there.
  * If a white screen comes back on the R4: run ysmenu_extinfo.py on the new ROM, then the GDB recipe above.

VERIFIED
  HeartGold R4FIX-v1/v2 (md5 1b019af5e51a316e99dd0d0b95af05de): boots in melonDS with YSMenu's records written;
  at InitSystemForTheGame all three places hold the build's own bytes again. CONFIRMED ON THE OWNER'S R4 (2026-10-16).
  Emulated nds-bootstrap v1.5.4 (B4DS): boots, none of its patches touch these addresses.
  Platinum R4FIX-v1: boots with YSMenu's record written; restored by InitSystem.

WHY NoDSProt-v1 WORKED AND THE BUILDS AROUND IT DID NOT (found 2026-10-16 by matching each build's code against the R4FIX map)
  YSMenu's addresses are fixed; the SDK file-system code (nitro.o) moves up every time game code is added before it,
  so the 8-byte jump at 0x020D8C14 walks backwards through the file-system functions build by build:
      09-22 (HWCRASH era)          FS_WaitAsync+0x20           used while files load        -> white screen (ENTRY AO report)
      09-27 (QOL-v14)              FS_UnloadArchiveTables+0x84
      10-04 .. 10-05 (DonorSlot)   FS_SuspendArchive+0x1C       never called in normal play  -> boots; the in-game crashes of
                                                                                                these builds were DSProt's heap leak
      10-05 NoDSProt-v1            FS_SuspendArchive+0x48       never called in normal play  -> boots, and DSProt (the crash
                                                                                                cause) is gone: "works perfectly"
      10-11 LegendBreed, ARCEUS    FS_UnloadArchive+0x50/+0x28                               -> white screen on the R4
      10-16 AIKNOW-v0              FSi_SendCommand+0xF4         every file read              -> white screen
      R4FIX                        FSi_SendCommand+0x58         undone by the guard          -> boots (confirmed on the R4)
  The second write (0x020D8C4C) is a branch into YSMenu's hook (B 0x023FC400) a few instructions further into the same
  function. The Thumb write at 0x0201A570 landed in Main_SetHBlankIntrCB+0xC (an HBlank callback setter, rarely used) in the
  10-04/10-05 builds. LegendBreed still reached the opening in melonDS with the patch applied, so exactly when the R4 calls
  FS_UnloadArchive at startup was not pinned down.

MODERN NDS-BOOTSTRAP (HeartGold ENTRY DW, 2026-10-16)
  Symptom: on the DS Lite (R4 with nds-bootstrap, flashcart/B4DS mode) R4FIX-v2 stopped on nds-bootstrap's red screen
  "Error: Data Abort!", PC 0x0200022C, ADDR 0x00000000.
  Cause: nds-bootstrap v2.x carries its own anti-piracy fix pack (nitro:/apfix.pck inside nds-bootstrap-release.nds;
  a file _nds/nds-bootstrap/apFix/<GAMECODE>-<CRC16>.ips or <GAMECODE>.ips on the SD card takes priority). The pack
  entry for IPKE matches ANY checksum (0xFFFF) - v1.5.x never did this. It is a 79-byte IPS applied to the
  decompressed ARM9 (an IPS offset 0x4000 + n means RAM 0x02000000 + n):
      0x02000228  56 bytes  hook code over unused secure-area filler (harmless by itself)
      0x020D8C1C   4 bytes  81 9D FC EB = bl 0x02000228   (the original game's anti-piracy spot, next to YSMenu's)
  In this mod 0x020D8C1C is inside FSi_SendCommand, so the first file read calls the hook with the wrong registers:
  "ldmia r5, {r0, r1}" with r5 = 0 -> Data Abort at 0x0200022C reading address 0.
  Proof: melonDS + nds-bootstrap v2.16.0 (B4DS, DLDI): IPKE -> white screen, log "AP-fix applied"; the same ROM with
  game code IPKX -> boots. A GDB RAM dump at NitroMain shows these two records are the only AP-fix changes.
  Fix, first try (ENTRY DW, NDSBFIX-v1): a 4th place in gYSMenuGuard (src/main.c). Booted in melonDS in all cases, but
  WHITE SCREEN ON THE OWNER'S DS LITE WITH BOTH YSMenu AND nds-bootstrap. Its YSMenu handling was identical to R4FIX-v2;
  the only other change was that every function after main.c moved 0x18 bytes. Some hardware-only effect that melonDS
  (built-in replacement BIOS) does not show depends on the layout - LegendBreed was the same: fine in the melonDS YSMenu
  simulation, white screen on the R4.
  Fix, current (ENTRY DX, NDSBFIX-v2): keep R4FIX-v2's code layout exactly.
      src/main.c          byte-for-byte the R4FIX-v2 version (YSMenu guard unchanged)
      src/loader_guard.c  gNdsBootstrapGuard ("NDSB_GUARD_V1", 0x020D8C1C) + LoaderGuard_StartUp(), ARM code
      main.lsf            src/loader_guard.o is the LAST object of the static module (after all other code)
      lib/asm/crt0.s      "bl NitroStartUp" (empty stub) -> "bl LoaderGuard_StartUp": same size, runs after unpacking,
                          autoload and BSS clear, just before NitroMain
      ysmguard.c          fills both tables (YSMENU_GUARD_V1, NDSB_GUARD_V1)
  Every function of the static module stays at its R4FIX-v2 address; only data moved (0xE0, it follows the code).
  RULE FOR LATER CHANGES TO THIS GUARD: do not add code to main.c or anything linked before nitro.o for it - put it in
  loader_guard.c, which is linked last. (Normal game changes still move code; the runtime undo covers that, as R4FIX-v2
  proved for YSMenu.) The hook bytes at 0x02000228 stay but are never called. A newer TWiLight on a 3DS/DSi would apply the
  same patch in DSi mode; this covers it too.
  Platinum: apfix.pck has no CPUE entry (only HG/SS: IPKx, IPGx), so Platinum needs nothing.
  Check a newer nds-bootstrap: extract nitro:/apfix.pck from nds-bootstrap-release.nds (16-byte entries from 0x10:
  game code[4], u16 crc (0xFFFF = any), u32 offset, u32 size), decode the IPKE IPS and compare its addresses with
  the guard table in src/main.c.
  Verified in melonDS (NDSBFIX-v2, md5 0ac8862a4bbe1d11a04d62ff063f0a0a): nds-bootstrap v2.16.0 -> LoaderGuard_StartUp is
  entered from crt0 with nds-bootstrap's call in place, NitroMain sees the build's own bytes, boots into the intro; YSMenu
  simulation and plain boot boot into the intro. Not yet confirmed on the DS Lite.

NDS-BOOTSTRAP-ONLY COPY (ENTRY DY)
  tools/ysmguard/make_ndsb_copy.py <in.nds> <out.nds> changes only the header game code (IPKE -> IPKX) and the header CRC.
  nds-bootstrap then applies no anti-piracy fix at all, and the code stays byte-identical to the input build.
  First made from R4FIX-v2: test_roms/pokeheartgold_R4FIX-v2-NDSBOOTSTRAP.nds. Use it with nds-bootstrap / TWiLight only;
  YSMenu keeps the IPKE build (it picks the save type by game code). Rename the save to match the new file name.
