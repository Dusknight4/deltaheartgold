#include "overlay_124.h"

#include "global.h"

#include "field_system.h"
#include "follow_mon.h"
#include "main.h"
#include "map_events.h"
#include "save_local_field_data.h"
#include "unk_02092BB8.h"
#include "unk_02092BE8.h"

// ANTI-PIRACY REMOVAL (2026-10-05, Changelog ENTRY DN): the DSProt flashcart/emulator/dummy detection that used to run
// here (it loaded the ds_protect overlay, ran six detection calls and fed a prime-number key into two "% 2441" /
// "% 4073" tests that called an allocate-and-never-free punishment) is gone. On genuine hardware every detection
// result was 0, both tests were false and the punishment was never called, so this is exactly the genuine-cartridge
// behaviour. The original is in backups/2026-10-05_dsprot-removal-v0_pre/src/overlay_124.c.
void FieldSystem_Init(OverlayManager *man, FieldSystem *fieldSystem) {
    UnkStruct_02111868_sub *args = OverlayManager_GetArgs(man);
    fieldSystem->saveData = args->saveData;
    fieldSystem->taskman = NULL;
    fieldSystem->location = LocalFieldData_GetCurrentPosition(Save_LocalFieldData_Get(fieldSystem->saveData));
    fieldSystem->mapMatrix = MapMatrix_New();
    Field_AllocateMapEvents(fieldSystem, HEAP_ID_FIELD2);
    fieldSystem->bagCursor = BagCursor_New(HEAP_ID_FIELD2);
    fieldSystem->unkA8 = UnkStruct_02092BB8_New(HEAP_ID_FIELD2);
    fieldSystem->unk108 = FieldSystem_UnkSub108_Alloc(HEAP_ID_FIELD2);
    fieldSystem->phoneRingManager = GearPhoneRingManager_New(HEAP_ID_FIELD2, fieldSystem);
    fieldSystem->judgeStatPosition = 0;
}
