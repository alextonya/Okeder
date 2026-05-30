from bot.fsm.states import BotState

VALID_TRANSITIONS: dict[BotState, list[BotState]] = {
    BotState.DM_CONSENT_CHECK:   [BotState.DM_BUDGET],
    BotState.DM_BUDGET:          [BotState.DM_AVAILABILITY],
    BotState.DM_AVAILABILITY:    [BotState.DM_PREFERENCES],
    BotState.DM_PREFERENCES:     [BotState.DM_CONFIRM_SUBMIT],
    BotState.DM_CONFIRM_SUBMIT:  [],  # terminal
    BotState.RATING_PROMPT:      [BotState.RATING_RECEIVED],
    BotState.RATING_RECEIVED:    [],  # terminal
}
