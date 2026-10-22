#ifndef POKEHEARTGOLD_TRAINER_AI_H
#define POKEHEARTGOLD_TRAINER_AI_H

#include "battle.h"

void ov10_0221BE20(BattleSystem *battleSystem, BattleContext *ctx, u8 battlerId, u8 a3);
u8 ov10_0221BEF4(BattleSystem *battleSystem, u8 battlerId);

// the following functions are in reality static but need to be decompiled still or are used by non-decompiled functions
u8 ov10_0221BF44(BattleSystem *battleSystem, BattleContext *ctx);
u8 ov10_0221C038(BattleSystem *battleSystem, BattleContext *ctx);


// ENTRY DP (2026-10-11): called from asm/overlay_10_trainer_ai.s and asm/overlay_12_battle_controller_opponent.s
// (declarations restored 2026-10-17 after the bisection snapshot missed this header; see ENTRY EG)
void TrainerAI_WonderGuardOverride(BattleSystem *battleSystem, BattleContext *ctx);
u8 ov10_022205BC(BattleSystem *battleSystem, u8 battlerId); // asm/overlay_10_trainer_ai.s: AI switch / item decision
u8 TrainerAI_PickCommandHidden(BattleSystem *battleSystem, u8 battlerId);

#endif
