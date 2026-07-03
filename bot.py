import asyncio
from contextlib import suppress
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot_profile import setup_bot_profile
from app.config import load_config
from app.database.storage import Database
from app.handlers import setup_routers
from app.logging_config import setup_logging
from app.middlewares import CallbackAnswerMiddleware, LoggingMiddleware
from app.services.backups import start_backup_scheduler


logger = logging.getLogger(__name__)


async def main() -> None:
    config = load_config()
    setup_logging()

    database = Database(config.database_path)
    await database.connect()
    await database.init_schema()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher["db"] = database
    dispatcher["backup_chat_id"] = config.backup_chat_id
    dispatcher.message.outer_middleware(LoggingMiddleware())
    dispatcher.callback_query.outer_middleware(LoggingMiddleware())
    dispatcher.callback_query.middleware(CallbackAnswerMiddleware())
    setup_routers(dispatcher)

    backup_task: asyncio.Task | None = None
    if config.backup_chat_id is None:
        logger.warning("BACKUP_CHAT_ID не задан: автоматические бэкапы выключены")
    else:
        backup_task = start_backup_scheduler(
            bot=bot,
            database_path=config.database_path,
            backup_chat_id=config.backup_chat_id,
        )

    try:
        await setup_bot_profile(bot)
        await dispatcher.start_polling(bot)
    finally:
        if backup_task is not None:
            backup_task.cancel()
            with suppress(asyncio.CancelledError):
                await backup_task
        await database.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
