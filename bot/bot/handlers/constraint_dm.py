"""
ConversationHandler FSM : collecte des contraintes par DM privé.
États : DM_CONSENT_CHECK → DM_BUDGET → DM_AVAILABILITY → DM_PREFERENCES → DM_CONFIRM_SUBMIT
"""
import re

import httpx
from telegram import Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from bot.config import settings
from bot.fsm.states import BotState
from bot.keyboards.consent_kb import consent_keyboard
from bot.templates.messages import (
    AVAILABILITY_QUESTION,
    BUDGET_QUESTION,
    CONFIRM_SUMMARY,
    PREFERENCES_DECLINED,
    PREFERENCES_QUESTION,
    PREFERENCES_SUBMITTED,
)


async def start_constraint_flow(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """/start_preferences_{event_id} — déclenche le DM de collecte."""
    if not update.message:
        return ConversationHandler.END

    text = update.message.text or ""
    match = re.search(r"start_preferences_([a-f0-9-]{36})", text)
    if not match:
        return ConversationHandler.END

    event_id = match.group(1)
    context.user_data["event_id"] = event_id

    await update.message.reply_text(
        "👋 A group outing is being planned!\n\nI'll ask you 3 quick questions privately. Ready?",
        reply_markup=consent_keyboard(event_id),
        parse_mode="HTML",
    )
    return BotState.DM_CONSENT_CHECK


async def consent_accept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    event_id = query.data.split(":")[2]
    context.user_data["event_id"] = event_id

    await query.edit_message_text(BUDGET_QUESTION, parse_mode="HTML")
    return BotState.DM_BUDGET


async def consent_decline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    event_id = query.data.split(":")[2]

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{settings.backend_api_url}/internal/telegram/preference-declined",
            json={
                "event_id": event_id,
                "telegram_user_id": query.from_user.id,
            },
        )

    await query.edit_message_text(PREFERENCES_DECLINED, parse_mode="HTML")
    return ConversationHandler.END


async def receive_budget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["budget_raw"] = update.message.text
    await update.message.reply_text(AVAILABILITY_QUESTION, parse_mode="HTML")
    return BotState.DM_AVAILABILITY


async def receive_availability(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["availability_raw"] = update.message.text
    await update.message.reply_text(PREFERENCES_QUESTION, parse_mode="HTML")
    return BotState.DM_PREFERENCES


async def receive_preferences(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["preferences_raw"] = update.message.text

    summary = CONFIRM_SUMMARY.format(
        budget=context.user_data.get("budget_raw", "—"),
        availability=context.user_data.get("availability_raw", "—"),
        preferences=context.user_data.get("preferences_raw", "—"),
    )

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Submit", callback_data="submit:confirm"),
        InlineKeyboardButton("✏️ Edit", callback_data="submit:edit"),
    ]])
    await update.message.reply_text(summary, reply_markup=keyboard, parse_mode="HTML")
    return BotState.DM_CONFIRM_SUBMIT


async def confirm_submit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    event_id = context.user_data.get("event_id")
    user = query.from_user

    async with httpx.AsyncClient() as client:
        await client.post(
            f"{settings.backend_api_url}/internal/telegram/submit-preferences",
            json={
                "event_id": event_id,
                "telegram_user_id": user.id,
                "budget_raw": context.user_data.get("budget_raw"),
                "availability_raw": context.user_data.get("availability_raw"),
                "preferences_raw": context.user_data.get("preferences_raw"),
            },
        )

    await query.edit_message_text(PREFERENCES_SUBMITTED, parse_mode="HTML")
    context.user_data.clear()
    return ConversationHandler.END


async def edit_restart(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(BUDGET_QUESTION, parse_mode="HTML")
    return BotState.DM_BUDGET


def build_constraint_conversation() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[CommandHandler("start", start_constraint_flow)],
        states={
            BotState.DM_CONSENT_CHECK: [
                CallbackQueryHandler(consent_accept, pattern=r"^consent:accept:"),
                CallbackQueryHandler(consent_decline, pattern=r"^consent:decline:"),
            ],
            BotState.DM_BUDGET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_budget)
            ],
            BotState.DM_AVAILABILITY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_availability)
            ],
            BotState.DM_PREFERENCES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_preferences)
            ],
            BotState.DM_CONFIRM_SUBMIT: [
                CallbackQueryHandler(confirm_submit, pattern=r"^submit:confirm"),
                CallbackQueryHandler(edit_restart, pattern=r"^submit:edit"),
            ],
        },
        fallbacks=[],
        per_chat=False,
        per_user=True,
    )
