#include "application/pokedex/pokedex_internal.h"

#include "dex_mon_measures.h"
#include "overlay_18.h"
#include "sound_02004A44.h"

BOOL Pokedex_Init(OverlayManager *man, int *state) {
    PokedexAppData *appData;

    Heap_Create(HEAP_ID_3, HEAP_ID_POKEDEX_APP, 0x61000);
    appData = OverlayManager_CreateAndGetData(man, sizeof(PokedexAppData), HEAP_ID_POKEDEX_APP);
    MI_CpuClear8(appData, sizeof(PokedexAppData));
    appData->args = OverlayManager_GetArgs(man);
    appData->unk_085C = 5;
    appData->unk_1858 = UnkStruct_02092BB8_GetUnk2(appData->args->unk_08);
    if (Pokedex_GetNatDexFlag(appData->args->pokedex)) {
        appData->unk_1860 = TRUE;
        if (appData->unk_1858 == 2) {
            appData->unk_1858 = 1;
        }
    } else {
        appData->unk_1860 = FALSE;
        if (appData->unk_1858 == 2) {
            appData->unk_1858 = 0;
        }
    }
    if (Pokedex_CheckMonCaughtFlag(appData->args->pokedex, SPECIES_GIRATINA) == TRUE) {
        SetDexBanksByGiratinaForm(Pokedex_GetSeenFormByIdx(appData->args->pokedex, SPECIES_GIRATINA, 0));
    } else {
        SetDexBanksByGiratinaForm(GIRATINA_ALTERED);
    }
    GF_SndHandleSetPlayerVolume(1, 42);
    appData->unk_185C = 2;
    return TRUE;
}

BOOL Pokedex_Main(OverlayManager *man, int *state) {
    PokedexAppData *appData = OverlayManager_GetData(man);

    if (!PokedexApp_RunMainSeq(appData, state)) {
        return TRUE;
    } else {
        return FALSE;
    }
}

BOOL Pokedex_Exit(OverlayManager *man, int *state) {
    PokedexAppData *appData = OverlayManager_GetData(man);

    // ANTI-PIRACY REMOVAL (2026-10-05, Changelog ENTRY DN): the three DSProt detection calls (and the ds_protect overlay load/
    // unload around them) that used to run here are gone; their callbacks were already empty (ENTRY AX).
    UnkStruct_02092BB8_Set(appData->args->unk_08, ov18_021F8838(appData), appData->unk_1858);
    OverlayManager_FreeData(man);
    Heap_Destroy(HEAP_ID_POKEDEX_APP);
    GF_SndHandleSetPlayerVolume(1, 127);
    sub_02004B10();
    return TRUE;
}
