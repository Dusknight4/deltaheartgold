#include "battle/trainer_ai.h"

#include "global.h"

#include "constants/abilities.h"
#include "constants/battle.h"
#include "constants/moves.h"
#include "constants/species.h"

#include "battle/battle.h"
#include "battle/battle_system.h"
#include "battle/overlay_12_0224E4FC.h"

#include "pokemon.h"

// ---------------------------------------------------------------------------------------------------------------------
// ENTRY EJ (2026-10-18) - THIS FUNCTION MUST BE THE VERY FIRST THING IN OVERLAY 10 (see Object order of OVY_10 in main.lsf).
//
// OVY_7, OVY_8 (the party / bag screens of a battle) and OVY_10 (the trainer AI) are loaded one at a time into the SAME RAM
// slot (ov12_02237ED0 / ov12_02237B0C / ov12_02237BB8). In the unmodified game each of them starts with a function at the same
// address (ov07_0221BE20 / ov08_0221BE20 / ov10_0221BE20), and the opponent controller in the always-loaded overlay 12
// (asm/overlay_12_battle_controller_opponent.s, three "bl ov10_0221BE20") calls that address once more right after the party
// screen has been opened - when OVY_8 is the overlay that is in the slot. That call has always run OVY_8's own first function,
// which happens to be harmless. If any code is placed in front of this function in overlay 10 (ENTRY DP / DT did exactly that),
// the call lands in the middle of OVY_8 instead: the CPU runs into garbage and the game freezes the moment the party screen is
// opened in a battle (real hardware and emulator, wild and trainer battles).
//
// Keeping this function alone in its own object file that is linked first pins it to offset 0 of the overlay whatever is added to
// trainer_ai.c later. tools/build_heartgold.sh verifies the address after every link.
// ---------------------------------------------------------------------------------------------------------------------

void ov10_0221BE20(BattleSystem *battleSystem, BattleContext *ctx, u8 battlerId, u8 a3) {
    int i;
    u8 struggleFlags;
    u8 *aiData = (u8 *)&ctx->trainerAIData;

    for (i = 0; i < OFFSET_OF(TrainerAIData *, moves); i++) {
        aiData[i] = 0;
    }

    for (i = 0; i < MAX_MON_MOVES; i++) {
        if (a3 & 1) {
            ctx->trainerAIData.movePoints[i] = 100;
        } else {
            ctx->trainerAIData.movePoints[i] = 0;
        }
        a3 >>= 1;
    }

    struggleFlags = StruggleCheck(battleSystem, ctx, battlerId, 0, -1);

    for (i = 0; i < MAX_MON_MOVES; i++) {
        if (struggleFlags & MaskOfFlagNo(i)) {
            ctx->trainerAIData.movePoints[i] = 0;
        }
        ctx->trainerAIData.unk18[i] = 100 - (BattleSystem_Random(battleSystem) % 16);
    }

    ctx->trainerAIData.unk98 = 0;

    if (battleSystem->battleType & BATTLE_TYPE_ROAMER) {
        ctx->trainerAIData.aiFlags = AI_29;
    } else {
        ctx->trainerAIData.aiFlags = battleSystem->trainers[battlerId].data.aiFlags;
    }

    if (battleSystem->battleType & BATTLE_TYPE_DOUBLES) {
        ctx->trainerAIData.aiFlags |= AI_DOUBLES;
    }
}
