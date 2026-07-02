from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from app.texts import (
    FAMILY_BUTTON,
    RECIPES_BUTTON,
    SHOPPING_BUTTON,
    WEEKLY_MENU_BUTTON,
)


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=RECIPES_BUTTON),
                KeyboardButton(text=WEEKLY_MENU_BUTTON),
            ],
            [
                KeyboardButton(text=SHOPPING_BUTTON),
                KeyboardButton(text=FAMILY_BUTTON),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел",
    )
