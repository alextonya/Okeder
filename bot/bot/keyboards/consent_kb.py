from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def consent_keyboard(event_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Yes, let's go!", callback_data=f"consent:accept:{event_id}"),
        InlineKeyboardButton("❌ Not this time", callback_data=f"consent:decline:{event_id}"),
    ]])
