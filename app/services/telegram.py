from __future__ import annotations

import logging
from typing import Any

from aiogram.exceptions import TelegramBadRequest


logger = logging.getLogger(__name__)

MESSAGE_NOT_MODIFIED = "message is not modified"
MESSAGE_TO_EDIT_NOT_FOUND = "message to edit not found"
QUERY_IS_TOO_OLD = "query is too old"


async def safe_edit_text(message: Any, text: str, reply_markup=None):
    try:
        return await message.edit_text(text, reply_markup=reply_markup)
    except TelegramBadRequest as error:
        error_text = str(error).lower()
        if MESSAGE_NOT_MODIFIED in error_text:
            logger.debug("Telegram edit ignored: message is not modified")
            return None
        if MESSAGE_TO_EDIT_NOT_FOUND in error_text or QUERY_IS_TOO_OLD in error_text:
            logger.info("Telegram edit fallback to new message: %s", error)
            return await message.answer(text, reply_markup=reply_markup)
        raise
