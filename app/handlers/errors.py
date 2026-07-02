from __future__ import annotations

import logging

from aiogram import Router
from aiogram.types import ErrorEvent


router = Router(name="errors")
logger = logging.getLogger(__name__)
USER_ERROR_TEXT = "Что-то пошло не так, попробуйте ещё раз."


@router.errors()
async def global_error_handler(event: ErrorEvent) -> bool:
    logger.exception("Необработанная ошибка", exc_info=event.exception)

    message = None
    if event.update.callback_query and event.update.callback_query.message:
        message = event.update.callback_query.message
    elif event.update.message:
        message = event.update.message

    if message is not None:
        try:
            await message.answer(USER_ERROR_TEXT)
        except Exception:
            logger.exception("Не удалось отправить сообщение об ошибке пользователю")

    return True
