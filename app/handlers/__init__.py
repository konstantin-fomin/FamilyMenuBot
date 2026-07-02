from aiogram import Dispatcher

from app.handlers import family, menu, recipes, start


def setup_routers(dispatcher: Dispatcher) -> None:
    dispatcher.include_router(start.router)
    dispatcher.include_router(family.router)
    dispatcher.include_router(recipes.router)
    dispatcher.include_router(menu.router)
