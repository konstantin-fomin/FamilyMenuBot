import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.config import load_config
from app.database.storage import Database
from app.handlers import setup_routers


async def main() -> None:
    config = load_config()
    logging.basicConfig(level=logging.INFO)

    database = Database(config.database_path)
    await database.connect()
    await database.init_schema()

    bot = Bot(
        token=config.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dispatcher = Dispatcher()
    dispatcher["db"] = database
    setup_routers(dispatcher)

    try:
        await dispatcher.start_polling(bot)
    finally:
        await database.close()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
