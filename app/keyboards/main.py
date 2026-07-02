from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📚 Рецепты"),
                KeyboardButton(text="📅 Меню недели"),
            ],
            [
                KeyboardButton(text="🛒 Покупки"),
                KeyboardButton(text="👨‍👩‍👧 Семья"),
            ],
        ],
        resize_keyboard=True,
        input_field_placeholder="Выберите раздел",
    )
