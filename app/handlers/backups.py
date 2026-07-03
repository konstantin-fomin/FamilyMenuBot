from __future__ import annotations

import logging

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message

from app.database import Database
from app.handlers.common import ACCESS_DENIED_TEXT, require_user
from app.services.backups import send_database_backup


router = Router(name="backups")
logger = logging.getLogger(__name__)


@router.message(Command("chatid"))
async def chat_id_command(message: Message, db: Database) -> None:
    user = await require_user(message, db)
    if user is None:
        return
    if user.role != "owner":
        await message.answer(ACCESS_DENIED_TEXT)
        return

    await message.answer(f"ID текущего чата: <code>{message.chat.id}</code>")


@router.message(Command("backup"))
async def backup_command(
    message: Message,
    bot: Bot,
    db: Database,
    backup_chat_id: int | None,
) -> None:
    user = await require_user(message, db)
    if user is None:
        return
    if user.role != "owner":
        await message.answer(ACCESS_DENIED_TEXT)
        return
    if backup_chat_id is None:
        await message.answer("Бэкапы выключены: BACKUP_CHAT_ID не задан.")
        return

    await message.answer("Готовлю и отправляю бэкап базы.")
    try:
        backup = await send_database_backup(bot, db.path, backup_chat_id)
    except Exception:
        logger.exception("Не удалось отправить бэкап по команде /backup")
        await message.answer("Не удалось отправить бэкап. Подробности записаны в logs/bot.log.")
        return

    await message.answer(f"Бэкап отправлен: {backup.filename}")
