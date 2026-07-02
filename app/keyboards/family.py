from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def family_keyboard(is_owner: bool) -> InlineKeyboardMarkup | None:
    if not is_owner:
        return None

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пригласить", callback_data="family:invite")]
        ]
    )
