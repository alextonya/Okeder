from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def commitment_keyboard(proposal_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("👍 Interested", callback_data=f"commit:soft:{proposal_id}"),
        InlineKeyboardButton("✅ I'm In", callback_data=f"commit:confirmed:{proposal_id}"),
        InlineKeyboardButton("🔒 Lock In", callback_data=f"commit:hard:{proposal_id}"),
    ]])
