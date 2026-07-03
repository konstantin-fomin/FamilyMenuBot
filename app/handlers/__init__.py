from aiogram import Dispatcher

from app.handlers import backups, errors, family, menu, recipes, shopping, start, weekly_menu


def setup_routers(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(start.router)
    dispatcher.include_router(family.router)
    dispatcher.include_router(recipes.router)
    dispatcher.include_router(weekly_menu.router)
    dispatcher.include_router(shopping.router)
    dispatcher.include_router(menu.router)
    dispatcher.include_router(backups.router)
    dispatcher.include_router(errors.router)
