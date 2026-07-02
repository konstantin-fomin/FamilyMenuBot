from aiogram import Bot
from aiogram.types import BotCommand


async def setup_bot_profile(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Открыть главное меню"),
            BotCommand(command="help", description="Как пользоваться ботом"),
        ]
    )
    await bot.set_my_short_description(
        "Семейный планировщик меню, рецептов и покупок."
    )
    await bot.set_my_description(
        "Этот бот помогает семье хранить рецепты, планировать меню недели "
        "и собирать общий список покупок. Доступ только по приглашению владельца."
    )
