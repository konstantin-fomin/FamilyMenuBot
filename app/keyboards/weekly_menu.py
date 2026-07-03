from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database import Category, MenuItem, RecipeSummary
from app.keyboards.recipes import RECIPES_PAGE_SIZE
from app.services.menus import DAY_SHORT_NAMES


def weekly_menu_keyboard(offset: int) -> InlineKeyboardMarkup:
    switch_text = "➡️ Следующая неделя" if offset == 0 else "⬅️ Текущая неделя"
    switch_offset = 1 if offset == 0 else 0
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="➕ Добавить блюда", callback_data=f"wm:add:{offset}")],
            [InlineKeyboardButton(text="✏️ Изменить", callback_data=f"wm:edit:{offset}")],
            [InlineKeyboardButton(text=switch_text, callback_data=f"wm:home:{switch_offset}")],
        ]
    )


def weekly_menu_categories_keyboard(categories: list[Category], offset: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=f"{category.name} ({category.recipes_count})",
                callback_data=f"wm:cat:{offset}:{category.id}:0",
            )
        ]
        for category in categories
    ]
    keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data=f"wm:done:{offset}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def weekly_menu_recipes_keyboard(
    recipes: list[RecipeSummary],
    offset: int,
    category_id: int,
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=recipe.name,
                callback_data=f"wm:recipe:{offset}:{recipe.id}:{category_id}:{page}",
            )
        ]
        for recipe in recipes
    ]
    pages = max((total - 1) // RECIPES_PAGE_SIZE + 1, 1)
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"wm:cat:{offset}:{category_id}:{page - 1}",
            )
        )
    if page + 1 < pages:
        navigation.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"wm:cat:{offset}:{category_id}:{page + 1}",
            )
        )
    if navigation:
        keyboard.append(navigation)
    keyboard.append([InlineKeyboardButton(text="⬅️ Категории", callback_data=f"wm:add:{offset}")])
    keyboard.append([InlineKeyboardButton(text="✅ Готово", callback_data=f"wm:done:{offset}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def day_choice_keyboard(
    offset: int,
    recipe_id: int,
    category_id: int,
    page: int,
) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=name,
                callback_data=f"wm:day:{offset}:{recipe_id}:{day}:{category_id}:{page}",
            )
        ]
        for day, name in DAY_SHORT_NAMES.items()
    ]
    keyboard.append(
        [
            InlineKeyboardButton(
                text="📌 Без дня",
                callback_data=f"wm:day:{offset}:{recipe_id}:0:{category_id}:{page}",
            )
        ]
    )
    keyboard.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data=f"wm:cat:{offset}:{category_id}:{page}",
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def servings_choice_keyboard(
    offset: int,
    recipe_id: int,
    day: int | None,
    category_id: int,
    page: int,
    servings: int,
) -> InlineKeyboardMarkup:
    day_raw = day or 0
    lower_servings = max(servings - 1, 1)
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➖",
                    callback_data=f"wm:sv:set:{offset}:{recipe_id}:{day_raw}:{category_id}:{page}:{lower_servings}",
                ),
                InlineKeyboardButton(text=f"👥 {servings}", callback_data="wm:noop"),
                InlineKeyboardButton(
                    text="➕",
                    callback_data=f"wm:sv:set:{offset}:{recipe_id}:{day_raw}:{category_id}:{page}:{servings + 1}",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✅ Добавить",
                    callback_data=f"wm:sv:add:{offset}:{recipe_id}:{day_raw}:{category_id}:{page}:{servings}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=f"wm:recipe:{offset}:{recipe_id}:{category_id}:{page}",
                )
            ],
        ]
    )


def edit_menu_items_keyboard(items: list[MenuItem], offset: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=_item_button_text(item),
                callback_data=f"wm:item:{offset}:{item.id}",
            )
        ]
        for item in items
    ]
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"wm:home:{offset}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def menu_item_actions_keyboard(item_id: int, offset: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📆 Поменять день", callback_data=f"wm:move:{offset}:{item_id}")],
            [InlineKeyboardButton(text="➖ Убрать один повтор", callback_data=f"wm:dec:{offset}:{item_id}")],
            [InlineKeyboardButton(text="🗑 Убрать блюдо целиком", callback_data=f"wm:del:{offset}:{item_id}")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"wm:edit:{offset}")],
        ]
    )


def move_day_keyboard(item_id: int, offset: int) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=name,
                callback_data=f"wm:move_day:{offset}:{item_id}:{day}",
            )
        ]
        for day, name in DAY_SHORT_NAMES.items()
    ]
    keyboard.append(
        [
            InlineKeyboardButton(
                text="📌 Без дня",
                callback_data=f"wm:move_day:{offset}:{item_id}:0",
            )
        ]
    )
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data=f"wm:item:{offset}:{item_id}")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def _item_button_text(item: MenuItem) -> str:
    suffix = f" ×{item.count}" if item.count > 1 else ""
    deleted = " (рецепт удалён)" if item.recipe_id is None else ""
    return f"{item.recipe_name}{deleted} · 👥 {item.servings}{suffix}"
