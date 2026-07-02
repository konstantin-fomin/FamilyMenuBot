from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject


logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        self._log_event(event)
        try:
            return await handler(event, data)
        except Exception:
            logger.exception("Ошибка при обработке события")
            raise

    def _log_event(self, event: TelegramObject) -> None:
        if isinstance(event, Message):
            user = event.from_user
            logger.info(
                "message user_id=%s text=%r",
                user.id if user else None,
                event.text,
            )
            return

        if isinstance(event, CallbackQuery):
            logger.info(
                "callback user_id=%s data=%r",
                event.from_user.id,
                event.data,
            )
