"""
Point d'entrée du bot Telegram Okeder.
Mode polling en dev (TELEGRAM_USE_POLLING=true), webhook en prod.
"""
import logging

from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, MessageHandler, filters

from bot.config import settings
from bot.handlers.commitment import handle_commitment_callback
from bot.handlers.constraint_dm import build_constraint_conversation
from bot.handlers.error import error_handler
from bot.handlers.group_invoke import handle_group_mention
from bot.handlers.rating import handle_rating_callback

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def debug_all(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handler de debug — log tous les messages reçus."""
    logger.info(f"[DEBUG] Update reçu: {update}")


def build_app() -> Application:
    app = Application.builder().token(settings.telegram_bot_token).build()

    # Handler de debug — à supprimer après les tests
    from telegram.ext import TypeHandler
    app.add_handler(TypeHandler(Update, debug_all), group=-1)

    # ConversationHandler DM — doit être enregistré avant les handlers génériques
    app.add_handler(build_constraint_conversation())

    # Mention @OkederBot dans un groupe — insensible à la casse
    app.add_handler(
        MessageHandler(
            filters.ChatType.GROUPS & filters.TEXT,
            handle_group_mention,
        )
    )

    # Callbacks clavier inline
    app.add_handler(CallbackQueryHandler(handle_commitment_callback, pattern=r"^commit:"))
    app.add_handler(CallbackQueryHandler(handle_rating_callback, pattern=r"^rate:"))

    # Handler d'erreur global
    app.add_error_handler(error_handler)

    return app


def main() -> None:
    app = build_app()

    if settings.telegram_use_polling:
        logger.info("Starting Okeder bot in polling mode (dev)")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    else:
        logger.info(f"Starting Okeder bot in webhook mode: {settings.bot_webhook_url}")
        app.run_webhook(
            listen="0.0.0.0",
            port=8443,
            url_path=f"/bot/{settings.telegram_bot_token}",
            webhook_url=f"{settings.bot_webhook_url}/bot/{settings.telegram_bot_token}",
            secret_token=settings.bot_webhook_secret,
        )


if __name__ == "__main__":
    main()
