    .include "macros/btlcmd.inc"

    .data

    // ENTRY DQ: Arceus transforms into the type BattleSystem_TryArceusTransform picked (its battle types and form are already
    // changed). Same effect as subscript_0262_FormChange (Transform's sound, pixelate out, new form, pixelate in), for the
    // defender, after "<attacker> used <move>!" has finished.

_000:
    Wait
    CompareMonDataToValue OPCODE_FLAG_NOT, BATTLER_CATEGORY_DEFENDER, BMON_DATA_STATUS2, STATUS2_SUBSTITUTE, _017
    PlayBattleAnimation BATTLER_CATEGORY_DEFENDER, BATTLE_ANIMATION_SUB_OUT
    Wait
    RestoreSprite BATTLER_CATEGORY_DEFENDER
    Wait
    PlayBattleAnimation BATTLER_CATEGORY_DEFENDER, BATTLE_ANIMATION_SUB_IN
    Wait

_017:
    PlaySound BATTLER_CATEGORY_DEFENDER, SEQ_SE_DP_W100
    SetMosaic BATTLER_CATEGORY_DEFENDER, 8, 1
    Wait
    ChangeForm BATTLER_CATEGORY_DEFENDER
    PlaySound BATTLER_CATEGORY_DEFENDER, SEQ_SE_DP_W107
    SetMosaic BATTLER_CATEGORY_DEFENDER, 0, 1
    Wait
    // {0} transformed!
    PrintMessage msg_0197_00721, TAG_NICKNAME, BATTLER_CATEGORY_DEFENDER
    Wait
    WaitButtonABTime 30
    CompareMonDataToValue OPCODE_FLAG_NOT, BATTLER_CATEGORY_DEFENDER, BMON_DATA_STATUS2, STATUS2_SUBSTITUTE, _059
    PlayBattleAnimation BATTLER_CATEGORY_DEFENDER, BATTLE_ANIMATION_SUB_OUT
    Wait
    RefreshSprite BATTLER_CATEGORY_DEFENDER
    Wait
    PlayBattleAnimation BATTLER_CATEGORY_DEFENDER, BATTLE_ANIMATION_SUB_IN
    Wait

_059:
    End
