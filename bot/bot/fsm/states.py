from enum import IntEnum


class BotState(IntEnum):
    # DM collecte de contraintes (par membre par event)
    DM_CONSENT_CHECK    = 20
    DM_BUDGET           = 21
    DM_AVAILABILITY     = 22
    DM_PREFERENCES      = 23
    DM_CONFIRM_SUBMIT   = 24

    # Post-event
    RATING_PROMPT       = 50
    RATING_RECEIVED     = 51
