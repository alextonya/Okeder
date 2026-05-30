"""
Point d'entrée du bot Telegram Okeder.
Mode polling en dev, webhook en prod.
"""
import logging

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

from bot.config import settings
from bot.handlers.commitment import handle_commitment_callback
from bot.handlers.constraint_dm import build_constraint_conversation
from bot.handlers.group_invoke import handle_group_mention
from bot.handlers.rating import handle_rating_callback

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def build_app() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()

    # Conversation handler — DM collecte contraintes
    app.add_handler(build_constraint_conversation())

    # Mention @Okeder dans un groupe
    app.add_handler(
        MessageHandler(
            filters.Entity("mention") & filters.ChatType.GROUPS,
            handle_group_mention,
        )
    )

    # Callbacks clavier inline
    app.add_handler(CallbackQueryHandler(handle_commitment_callback, pattern=r"^commit:"))
    app.add_handler(CallbackQueryHandler(handle_rating_callback, pattern=r"^rate:"))

    return app


def main() -> None:
    app = build_app()

    if settings.telegram_use_polling:
        logger.info("Starting bot in polling mode (dev)")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    else:
        logger.info(f"Starting bot in webhook mode: {settings.bot_webhook_url}")
        app.run_webhook(
            listen="0.0.0.0",
            port=8443,
            url_path=f"/webhook/{settings.telegram_bot_token}",
            webhook_url=settings.bot_webhook_url,
            secret_token=settings.bot_webhook_secret,
        )


if __name__ == "__main__":
    main()
