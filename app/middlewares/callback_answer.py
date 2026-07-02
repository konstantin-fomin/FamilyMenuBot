from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, TelegramObject


logger = logging.getLogger(__name__)


def _is_stale_callback_error(error: TelegramBadRequest) -> bool:
    text = str(error).lower()
    return "query is too old" in text or "query id is invalid" in text


class CallbackAnswerMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)

        answered = False
        original_answer = event.answer

        async def tracked_answer(*args: Any, **kwargs: Any) -> Any:
            nonlocal answered
            answered = True
            try:
                return await original_answer(*args, **kwargs)
            except TelegramBadRequest as error:
                if _is_stale_callback_error(error):
                    logger.info("CallbackQuery уже устарел: %s", error)
                    return None
                raise

        object.__setattr__(event, "answer", tracked_answer)
        try:
            result = await handler(event, data)
            if not answered:
                try:
                    await original_answer()
                except TelegramBadRequest as error:
                    if _is_stale_callback_error(error):
                        logger.info("CallbackQuery уже устарел: %s", error)
                    else:
                        logger.exception("Не удалось ответить на callback-запрос")
            return result
        finally:
            object.__setattr__(event, "answer", original_answer)
