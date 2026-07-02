import asyncio
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.bot_profile import setup_bot_profile
from app.config import load_config
from app.database.storage import Database
from app.handlers import setup_routers
from app.logging_config import setup_logging
from app.middlewares import LoggingMiddleware


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
    dispatcher.message.outer_middleware(LoggingMiddleware())
    dispatcher.callback_query.outer_middleware(LoggingMiddleware())
    setup_routers(dispatcher)

    try:
        await setup_bot_profile(bot)
        await dispatcher.start_polling(bot)
    finally:
        await database.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
