import logging

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Exception while handling update:", exc_info=context.error)
    # Ne pas tenter d'envoyer un message d'erreur — ça échoue aussi avec le bug TLS
    # L'utilisateur verra juste que le bot ne répond pas, puis il réessaiera
