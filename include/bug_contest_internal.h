#ifndef POKEHEARTGOLD_BUG_CONTEST_INTERNAL_H
#define POKEHEARTGOLD_BUG_CONTEST_INTERNAL_H

#include "heap.h"
#include "party.h"
#include "pokemon.h"

typedef struct BUGMON {
    u16 species;
    u8 lvlmin;
    u8 lvlmax;
    u8 rate;
    u8 score;
    u8 dummy[2];
} BUGMON;

// QOL (2026-09-24): raised from 10 to 47 so every single Bug-type species in the game (checked
// against files/poketool/personal.json for every species with TYPE_BUG as either type) can appear
// in the Bug Catching Contest, each with at least a 1% encounter chance - see
// files/data/mushi/mushi_encount.csv and the simplified BugContest_InitEncounters (now always
// loads this one unified 47-species set instead of picking one of 4 day-of-week/dex-gated 10-entry
// sets, since a single table already covers the full roster with no need for daily rotation).
#define BUGMON_COUNT 47

// QOL (2026-09-26): this used to be a `static` array inside overlay_bug_contest.c (see the comment on
// BugContest's old `encounters` field below for why it was moved out of the heap-allocated struct in
// the first place), but that broke the contest completely: overlay_bug_contest.c compiles into the
// "bug_contest" overlay, which src/field/encounter_check.c's FieldSystem_GenerateBugContestEncounter
// loads and unloads via HandleLoadOverlay/UnloadOverlayByID around EVERY SINGLE wild-encounter check
// while walking around in the contest - reloading an overlay resets its own .bss to zero, so the
// encounter table was being wiped out immediately after every step, leaving every wild encounter as
// species 0 (SPECIES_NONE) at level 0.
//
// CRITICAL FOLLOW-UP (2026-09-27): the first fix for the above moved the actual 376-byte BUGMON array
// into src/field_system.c as a plain `BUGMON gBugContestEncounters[BUGMON_COUNT]` global - which fixed
// the wipe-on-reload bug, but permanently reserved 376 bytes of the MAIN STATIC MODULE's .bss for the
// entire game session (main is never unloaded, so this .bss is never reclaimed). This directly shrinks
// the total heap arena available to every heap in the game by that same amount, since the top-level
// heap pool is sized as "whatever RAM isn't already claimed by static .text/.data/.bss" at boot. That
// 376-byte reduction was apparently enough to push src/save.c's Save_GetSaveFilesStatus - which
// allocates TWO SAVE_PAGE_MAX*SAVE_SECTOR_SIZE buffers (~140 KB each, ~280 KB total) from HEAP_ID_3,
// the SAME heap the Bug Contest itself allocates from - past its available capacity on real hardware.
// Heap_AllocAtEnd's result there is never checked for NULL; when it silently fails, FlashLoadChunk is
// handed a NULL destination, both save mirrors are treated as unreadable/dummy, and the game reports
// LOAD_STATUS_NOT_EXIST - "no save file" - even though a perfectly valid save exists on the cartridge,
// and even for a save written moments earlier in the same broken session. This is now only a POINTER
// (4 bytes of permanent .bss instead of 376) - the actual BUGMON_COUNT-entry buffer is heap-allocated
// for the lifetime of one BugContest instance only (BugContest_New/BugContest_Delete), the same way
// bugContest->mon already is, so it costs heap capacity only while a contest is actually in progress,
// never permanently. The pointer itself still lives in the main static module, so it - and whatever it
// points to - both survive the "bug_contest" overlay being loaded/unloaded around every wild-encounter
// check, which is all the original fix above ever actually needed.
extern BUGMON *gBugContestEncounters;

typedef struct BugContestantData {
    u8 national;
    u8 day;
    u16 species;
    u16 score;
    u16 randmod;
} BugContestantData;

typedef struct BugContestant {
    u8 id;
    u16 score;
    BugContestantData data;
} BugContestant;

#define BUGCONTESTANT_NPC_COUNT 5
#define BUGCONTESTANT_PLAYER    BUGCONTESTANT_NPC_COUNT
#define BUGCONTESTANT_COUNT     (BUGCONTESTANT_NPC_COUNT + 1)

typedef struct BugContest {
    enum HeapID heapID;                             // Always set to 3
    SaveData *saveData;                             // Pointer to save data
    Party *party_bak;                               // Player's party is held for the contest
    Party *party_cur;                               // Only the lead Pokemon
    Pokemon *mon;                                   // The Pokemon you caught in the contest
    u8 lead_mon_idx;                                // Slot number of the Pokemon you battled with
    u8 party_cur_num;                               // Size of the party pre-contest
    u8 day_of_week;                                 // Used to choose NPCs and encounters
    u8 caught_poke : 1;                             // If you've caught a Pokemon in the contest
    u8 national_dex : 1;                            // Used to choose NPCs and encounters
    u8 placement : 6;                               // 0: First, 1: Second, 2: Third, 3: Consolation
    u16 sport_balls;                                // Set to 20, decremented on use
    u16 prize;                                      // Item ID
    u32 elapsed_time;                               // Used to determine when the contest ends
    // QOL (2026-09-26): encounters used to be embedded here directly, but growing BUGMON_COUNT
    // from 10 to 47 (see above) grew this struct by 296 bytes, which was enough to push the
    // Heap_Alloc(HEAP_ID_3, sizeof(BugContest)) call in BugContest_New past HEAP_ID_3's
    // available capacity on real hardware, returning NULL and crashing the very next line
    // (MI_CpuClear8) - a real-hardware regression the user reported as red-screen crashes on
    // entering/finishing the contest and on wild encounters near it. Since this table is
    // read-only game data (loaded once from mushi_encount.bin and never mutated per-instance),
    // it doesn't need to live inside the per-contest heap allocation at all - it's now a static
    // buffer in overlay_bug_contest.c instead, which costs zero runtime heap.
    BugContestant contestants[BUGCONTESTANT_COUNT]; // 5 NPCs + player
    u8 ranking[BUGCONTESTANT_COUNT];                // Index sorting by score at the end
} BugContest;

#endif // POKEHEARTGOLD_BUG_CONTEST_INTERNAL_H
