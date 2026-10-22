#include "battle/trainer_ai.h"

#include "global.h"

#include "constants/abilities.h"
#include "constants/battle.h"
#include "constants/moves.h"
#include "constants/species.h"

#include "battle/battle.h"
#include "battle/battle_system.h"
#include "battle/overlay_12_0224E4FC.h"

#include "filesystem.h"
#include "gf_gfx_loader.h"
#include "heap.h"
#include "item.h"
#include "pokemon.h"
#include "system.h"

// ---------------------------------------------------------------------------------------------------------------------
// ENTRY DT (replaces the first-turn-only hiding of ENTRY DP): the AI knows what a "maximum informed" player would know of the
// Pokemon it faces - see BattleAI_HideOpponentInfo in overlay_12_0224E4FC.c, which this calls around every decision. This
// overlay works out the move hints: a move a Pokemon was seen using that its species cannot learn (level-up, TM/HM, egg,
// tutor - its own or its base form's) can only be a per-type level-up move (ENTRY DS) or a TM it learned through its type,
// so it has one of those types. Once per move.
// ---------------------------------------------------------------------------------------------------------------------
#define AI_EGG_MOVE_LIST_ENTRIES 2045 // as LoadEggMoves (get_egg.c)
#define AI_EGG_MOVES_SPECIES     20000

// the order of the tutor learnset bits (sTutorMoves, src/field/scrcmd_move_tutor.c)
static const u16 sAITutorMoves[] = {
    MOVE_DIVE, MOVE_MUD_SLAP, MOVE_FURY_CUTTER, MOVE_ICY_WIND, MOVE_ROLLOUT, MOVE_THUNDER_PUNCH, MOVE_FIRE_PUNCH, MOVE_SUPERPOWER,
    MOVE_ICE_PUNCH, MOVE_IRON_HEAD, MOVE_AQUA_TAIL, MOVE_OMINOUS_WIND, MOVE_GASTRO_ACID, MOVE_SNORE, MOVE_SPITE, MOVE_AIR_CUTTER,
    MOVE_HELPING_HAND, MOVE_ENDEAVOR, MOVE_OUTRAGE, MOVE_ANCIENT_POWER, MOVE_SYNTHESIS, MOVE_SIGNAL_BEAM, MOVE_ZEN_HEADBUTT, MOVE_VACUUM_WAVE,
    MOVE_EARTH_POWER, MOVE_GUNK_SHOT, MOVE_TWISTER, MOVE_SEED_BOMB, MOVE_IRON_DEFENSE, MOVE_MAGNET_RISE, MOVE_LAST_RESORT, MOVE_BOUNCE,
    MOVE_TRICK, MOVE_HEAT_WAVE, MOVE_KNOCK_OFF, MOVE_SUCKER_PUNCH, MOVE_SWIFT, MOVE_UPROAR, MOVE_SUPER_FANG, MOVE_PAIN_SPLIT,
    MOVE_STRING_SHOT, MOVE_TAILWIND, MOVE_GRAVITY, MOVE_WORRY_SEED, MOVE_MAGIC_COAT, MOVE_ROLE_PLAY, MOVE_HEAL_BELL, MOVE_LOW_KICK,
    MOVE_SKY_ATTACK, MOVE_BLOCK, MOVE_BUG_BITE, MOVE_HEADBUTT,
};

static BOOL TrainerAI_SpeciesLearnsMove(int species, int form, u16 move) {
    int i, j;
    u16 *eggMoveList;
    u8 tutorLearnset[8];
    FSFile file;

    if (LevelUpLearnsetHasMove(species, form, move)) {
        return TRUE;
    }

    for (i = 0; i <= ITEM_HM08 - ITEM_TM01; i++) {
        if (TMHMGetMove(ITEM_TM01 + i) == move) {
            if (GetTMHMCompatBySpeciesAndForm(species, form, i)) {
                return TRUE;
            }
            break;
        }
    }

    // egg moves are listed for the species that hatches
    eggMoveList = GfGfxLoader_LoadFromNarc(NARC_fielddata_breeding_egg_move_list, 0, FALSE, HEAP_ID_BATTLE, TRUE);
    for (i = 0; i < AI_EGG_MOVE_LIST_ENTRIES; i++) {
        if (eggMoveList[i] == AI_EGG_MOVES_SPECIES + species) {
            for (j = i + 1; j < AI_EGG_MOVE_LIST_ENTRIES && eggMoveList[j] < AI_EGG_MOVES_SPECIES; j++) {
                if (eggMoveList[j] == move) {
                    Heap_Free(eggMoveList);
                    return TRUE;
                }
            }
            break;
        }
    }
    Heap_Free(eggMoveList);

    for (i = 0; i < (int)NELEMS(sAITutorMoves); i++) {
        if (sAITutorMoves[i] == move) {
            // waza_oshie.bin: 8 bytes per species from Bulbasaur (as GetMoveTutorLearnset)
            FS_InitFile(&file);
            if (species < 1 || !FS_OpenFile(&file, "fielddata/wazaoshie/waza_oshie.bin")) {
                return FALSE;
            }
            FS_SeekFile(&file, (species - 1) * sizeof(tutorLearnset), FS_SEEK_SET);
            FS_ReadFile(&file, tutorLearnset, sizeof(tutorLearnset));
            FS_CloseFile(&file);
            return (tutorLearnset[i / 8] >> (i % 8)) & 1;
        }
    }

    return FALSE;
}

static u32 TrainerAI_TypesExplainingMove(BattleContext *ctx, int species, int form, u16 move) {
    int baseSpecies = GetEggSpecies(species);
    u32 types = 0;
    u32 defaultTypes, baseTypes;
    int i;

    if (TrainerAI_SpeciesLearnsMove(species, form, move) || (baseSpecies != species && TrainerAI_SpeciesLearnsMove(baseSpecies, 0, move))) {
        return 0;
    }

    for (i = 0; i <= TYPE_DARK; i++) {
        if (IsTypeLevelUpMove(i, move)) {
            types |= MaskOfFlagNo(i);
        }
    }
    for (i = 0; i <= ITEM_HM08 - ITEM_TM01; i++) {
        if (TMHMGetMove(ITEM_TM01 + i) == move) {
            types |= MaskOfFlagNo(ctx->trainerAIData.moveData[move].type);
            break;
        }
    }

    // a type its base form had and it no longer has by default may have taught it the move before it evolved
    defaultTypes = MaskOfFlagNo(GetMonBaseStat_HandleAlternateForm(species, form, BASE_TYPE1)) | MaskOfFlagNo(GetMonBaseStat_HandleAlternateForm(species, form, BASE_TYPE2));
    baseTypes = MaskOfFlagNo(GetMonBaseStat_HandleAlternateForm(baseSpecies, 0, BASE_TYPE1)) | MaskOfFlagNo(GetMonBaseStat_HandleAlternateForm(baseSpecies, 0, BASE_TYPE2));
    if (types & baseTypes & ~defaultTypes) {
        return 0;
    }

    return types;
}

static void TrainerAI_UpdateMoveKnowledge(BattleSystem *battleSystem, BattleContext *ctx) {
    int owner, slot, i;

    if (BattleSystem_GetBattleType(battleSystem) & BATTLE_TYPE_LINK) {
        return;
    }

    for (owner = 0; owner < BATTLER_MAX; owner++) {
        for (slot = 0; slot < AI_KNOWLEDGE_PARTY_SLOTS; slot++) {
            AIMonKnowledge *knowledge = &ctx->aiMonKnowledge[owner][slot];

            for (i = 0; i < MAX_MON_MOVES; i++) {
                if (knowledge->seenMoves[i] != MOVE_NONE && !(knowledge->seenMoveTypes[i] & AI_KNOWLEDGE_MOVE_CHECKED)) {
                    Pokemon *mon = BattleSystem_GetPartyMon(battleSystem, owner, slot);

                    knowledge->seenMoveTypes[i] = AI_KNOWLEDGE_MOVE_CHECKED | TrainerAI_TypesExplainingMove(ctx, GetMonData(mon, MON_DATA_SPECIES, NULL), GetMonData(mon, MON_DATA_FORM, NULL), knowledge->seenMoves[i]);
                }
            }
        }
    }
}

// Moves a Wonder Guard target cannot stop the AI from using even though they do no damage: confusion, burn, poison and the
// two damaging weathers.
static BOOL TrainerAI_IsUsefulVsWonderGuard(u16 move) {
    switch (move) {
    case MOVE_CONFUSE_RAY:
    case MOVE_SUPERSONIC:
    case MOVE_SWEET_KISS:
    case MOVE_TEETER_DANCE:
    case MOVE_SWAGGER:
    case MOVE_FLATTER:
    case MOVE_WILL_O_WISP:
    case MOVE_TOXIC:
    case MOVE_POISON_POWDER:
    case MOVE_POISON_GAS:
    case MOVE_HAIL:
    case MOVE_SANDSTORM:
        return TRUE;
    }
    return FALSE;
}

// QOL (2026-10-11): if the AI believes its current target has Wonder Guard and none of its damaging moves is super effective,
// it no longer stalls with arbitrary status moves - it attacks anyway (the hits do nothing, but it keeps attacking), unless
// the status move is one of the useful ones above. Called from asm/overlay_10_trainer_ai.s (singles: ov10_0221BF44, doubles:
// ov10_0221C038) after the AI scripts scored the moves and before the best move is picked. Unusable moves keep score 0.
void TrainerAI_WonderGuardOverride(BattleSystem *battleSystem, BattleContext *ctx) {
    int i;
    int attacker = ctx->trainerAIData.battlerIdAttacker;
    int target = ctx->trainerAIData.battlerIdTarget;
    int known;
    u32 invalidMoves;
    u16 move;
    u32 flag;

    if ((target & 1) == (attacker & 1) || ctx->battleMons[attacker].ability == ABILITY_MOLD_BREAKER) {
        return;
    }

    // what the AI believes: a known (revealed) ability, else Wonder Guard if that is one of the species' own abilities
    known = ctx->trainerAIData.abilities[target];
    if (known == ABILITY_NONE) {
        if (GetMonBaseStat_HandleAlternateForm(ctx->battleMons[target].species, ctx->battleMons[target].form, BASE_ABILITY_1) == ABILITY_WONDER_GUARD
            || GetMonBaseStat_HandleAlternateForm(ctx->battleMons[target].species, ctx->battleMons[target].form, BASE_ABILITY_2) == ABILITY_WONDER_GUARD) {
            known = ABILITY_WONDER_GUARD;
        }
    }
    if (known != ABILITY_WONDER_GUARD) {
        return;
    }

    // any super-effective damaging move? then the normal scoring already handles it
    for (i = 0; i < MAX_MON_MOVES; i++) {
        move = ctx->battleMons[attacker].moves[i];

        if (move != MOVE_NONE && ctx->trainerAIData.moveData[move].power != 0) {
            flag = 0;
            ov12_02252054(ctx, move, 0, ctx->battleMons[attacker].ability, ABILITY_NONE, GetBattlerHeldItemEffect(ctx, target), ctx->battleMons[target].type1, ctx->battleMons[target].type2, &flag);
            if (flag & MOVE_STATUS_SUPER_EFFECTIVE) {
                return;
            }
        }
    }

    invalidMoves = StruggleCheck(battleSystem, ctx, attacker, 0, -1);

    for (i = 0; i < MAX_MON_MOVES; i++) {
        move = ctx->battleMons[attacker].moves[i];

        if (move == MOVE_NONE || (invalidMoves & MaskOfFlagNo(i))) {
            continue;
        }

        if (ctx->trainerAIData.moveData[move].power != 0) {
            if (ctx->trainerAIData.movePoints[i] < 100) {
                ctx->trainerAIData.movePoints[i] = 100;
            }
        } else if (!TrainerAI_IsUsefulVsWonderGuard(move)) {
            ctx->trainerAIData.movePoints[i] = 0;
        }
    }
}

// ENTRY EJ: ov10_0221BE20 (the AI data initialiser) was moved to src/battle/trainer_ai_init.c, which main.lsf links first in
// overlay 10 so that it stays at offset 0 of the overlay (a call to that address from overlay 12 runs OVY_8's first function while
// the party screen is open - do not put anything in front of it).

u8 ov10_0221BEF4(BattleSystem *battleSystem, u8 battlerId) {
    u8 ret;
    BattleContext *ctx = battleSystem->ctx;

    TrainerAI_UpdateMoveKnowledge(battleSystem, ctx); // ENTRY DT
    BattleAI_HideOpponentInfo(battleSystem, ctx, battlerId);

    if (!(ctx->trainerAIData.unk10 & 0x10)) {
        ctx->trainerAIData.battlerIdAttacker = battlerId;
        ctx->trainerAIData.battlerIdTarget = Battler_GetRandomOpposingBattlerId(battleSystem, ctx, battlerId);

        ov10_0221BE20(battleSystem, ctx, ctx->trainerAIData.battlerIdAttacker, 15);
    }

    if ((battleSystem->battleType & BATTLE_TYPE_DOUBLES) == 0) {
        ret = ov10_0221BF44(battleSystem, ctx);
    } else {
        ret = ov10_0221C038(battleSystem, ctx);
    }

    BattleAI_RestoreOpponentInfo(ctx);

    return ret;
}

// QOL (2026-10-11), ENTRY DT: the AI's switch / item decision (ov10_022205BC, called from
// asm/overlay_12_battle_controller_opponent.s) reads the opponent's ability and types directly (for example ov10_0221F62C,
// the "cannot damage Wonder Guard" check), so it gets the same knowledge as ov10_0221BEF4.
u8 TrainerAI_PickCommandHidden(BattleSystem *battleSystem, u8 battlerId) {
    BattleContext *ctx = battleSystem->ctx;
    u8 ret;

    TrainerAI_UpdateMoveKnowledge(battleSystem, ctx);
    BattleAI_HideOpponentInfo(battleSystem, ctx, battlerId);
    ret = ov10_022205BC(battleSystem, battlerId);
    BattleAI_RestoreOpponentInfo(ctx);

    return ret;
}
