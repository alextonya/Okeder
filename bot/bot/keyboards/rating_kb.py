from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def rating_keyboard(event_id: str) -> InlineKeyboardMarkup:
    stars = ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"]
    return InlineKeyboardMarkup([[
        InlineKeyboardButton(s, callback_data=f"rate:{i+1}:{event_id}")
        for i, s in enumerate(stars)
    ]])
