from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database import ShoppingItem
from app.services.shopping import shopping_item_button_text


SHOPPING_PAGE_SIZE = 25


def shopping_keyboard(
    items: list[ShoppingItem],
    offset: int,
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=shopping_item_button_text(item),
                callback_data=f"shop:toggle:{offset}:{item.id}:{page}",
            )
        ]
        for item in items
    ]
    pages = max((total - 1) // SHOPPING_PAGE_SIZE + 1, 1)
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(text="⬅️", callback_data=f"shop:page:{offset}:{page - 1}"))
    if page + 1 < pages:
        navigation.append(InlineKeyboardButton(text="➡️", callback_data=f"shop:page:{offset}:{page + 1}"))
    if navigation:
        keyboard.append(navigation)

    if total == 0:
        keyboard.append([InlineKeyboardButton(text="🧾 Собрать список из меню", callback_data=f"shop:rebuild:{offset}:0")])
    else:
        keyboard.append([InlineKeyboardButton(text="➕ Добавить своё", callback_data=f"shop:manual:{offset}")])
        keyboard.append([InlineKeyboardButton(text="🔄 Обновить из меню", callback_data=f"shop:rebuild:{offset}:{page}")])
        keyboard.append([InlineKeyboardButton(text="🧹 Убрать купленное", callback_data=f"shop:clear:{offset}:{page}")])

    switch_text = "➡️ Следующая неделя" if offset == 0 else "⬅️ Текущая неделя"
    switch_offset = 1 if offset == 0 else 0
    keyboard.append([InlineKeyboardButton(text=switch_text, callback_data=f"shop:page:{switch_offset}:0")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def clear_bought_confirm_keyboard(offset: int, page: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data=f"shop:clear_yes:{offset}:{page}"),
                InlineKeyboardButton(text="Нет", callback_data=f"shop:page:{offset}:{page}"),
            ]
        ]
    )
