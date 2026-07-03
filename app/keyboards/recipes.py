from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from app.database import Category, RecipeSummary


RECIPES_PAGE_SIZE = 8


def recipes_home_keyboard(categories: list[Category]) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить рецепт", callback_data="recipes:add")],
        [
            InlineKeyboardButton(text="🔍 Поиск", callback_data="recipes:search"),
            InlineKeyboardButton(text="📖 Все рецепты", callback_data="recipes:list:0:0"),
        ],
    ]
    keyboard.extend(
        [
            InlineKeyboardButton(
                text=f"{category.name} ({category.recipes_count})",
                callback_data=f"recipes:list:{category.id}:0",
            )
        ]
        for category in categories
    )
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def add_recipe_method_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 По шагам", callback_data="recipes:add_method:steps"),
                InlineKeyboardButton(text="⚡ Одним сообщением", callback_data="recipes:add_method:one"),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="recipes:cancel")],
        ]
    )


def categories_keyboard(categories: list[Category], prefix: str) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text=category.name, callback_data=f"{prefix}:{category.id}")]
        for category in categories
    ]
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="recipes:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def ingredients_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Верно", callback_data="recipes:add:ingredients_ok"),
                InlineKeyboardButton(text="✏️ Исправить", callback_data="recipes:add:ingredients_retry"),
            ],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="recipes:cancel")],
        ]
    )


def steps_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="recipes:add:skip_steps")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="recipes:cancel")],
        ]
    )


def photo_skip_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Пропустить", callback_data="recipes:add:skip_photo")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="recipes:cancel")],
        ]
    )


def save_recipe_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💾 Сохранить", callback_data="recipes:add:save"),
                InlineKeyboardButton(text="❌ Отмена", callback_data="recipes:cancel"),
            ]
        ]
    )


def one_message_confirm_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💾 Сохранить", callback_data="recipes:add:save")],
            [InlineKeyboardButton(text="✏️ Исправить", callback_data="recipes:add:one_retry")],
            [InlineKeyboardButton(text="❌ Отмена", callback_data="recipes:cancel")],
        ]
    )


def recipes_list_keyboard(
    recipes: list[RecipeSummary],
    category_id: int,
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=recipe.name,
                callback_data=f"recipes:view:{recipe.id}:{category_id}:{page}",
            )
        ]
        for recipe in recipes
    ]
    pages = max((total - 1) // RECIPES_PAGE_SIZE + 1, 1)
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"recipes:list:{category_id}:{page - 1}")
        )
    if page + 1 < pages:
        navigation.append(
            InlineKeyboardButton(text="➡️", callback_data=f"recipes:list:{category_id}:{page + 1}")
        )
    if navigation:
        keyboard.append(navigation)
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="recipes:home")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def search_results_keyboard(
    recipes: list[RecipeSummary],
    page: int,
    total: int,
) -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                text=recipe.name,
                callback_data=f"recipes:view:{recipe.id}:-1:{page}",
            )
        ]
        for recipe in recipes
    ]
    pages = max((total - 1) // RECIPES_PAGE_SIZE + 1, 1)
    navigation = []
    if page > 0:
        navigation.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"recipes:search_page:{page - 1}")
        )
    if page + 1 < pages:
        navigation.append(
            InlineKeyboardButton(text="➡️", callback_data=f"recipes:search_page:{page + 1}")
        )
    if navigation:
        keyboard.append(navigation)
    keyboard.append([InlineKeyboardButton(text="📖 Все рецепты", callback_data="recipes:list:0:0")])
    keyboard.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="recipes:home")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def recipe_card_keyboard(recipe_id: int, category_id: int, page: int) -> InlineKeyboardMarkup:
    back_callback = (
        f"recipes:search_page:{page}"
        if category_id == -1
        else f"recipes:list:{category_id}:{page}"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"recipes:edit:{recipe_id}"),
                InlineKeyboardButton(text="🗑 Удалить", callback_data=f"recipes:delete:{recipe_id}"),
            ],
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data=back_callback,
                )
            ],
        ]
    )


def edit_recipe_keyboard(recipe_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Название", callback_data=f"recipes:edit_field:{recipe_id}:name")],
            [InlineKeyboardButton(text="Категорию", callback_data=f"recipes:edit_field:{recipe_id}:category")],
            [InlineKeyboardButton(text="Ингредиенты", callback_data=f"recipes:edit_field:{recipe_id}:ingredients")],
            [InlineKeyboardButton(text="Шаги", callback_data=f"recipes:edit_field:{recipe_id}:steps")],
            [InlineKeyboardButton(text="🖼 Фото", callback_data=f"recipes:edit_field:{recipe_id}:photo")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data=f"recipes:view:{recipe_id}:0:0")],
        ]
    )


def edit_photo_keyboard(recipe_id: int, has_photo: bool) -> InlineKeyboardMarkup:
    keyboard = []
    if has_photo:
        keyboard.append(
            [InlineKeyboardButton(text="🗑 Удалить фото", callback_data=f"recipes:edit_photo_delete:{recipe_id}")]
        )
    keyboard.append([InlineKeyboardButton(text="❌ Отмена", callback_data="recipes:cancel")])
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def delete_confirm_keyboard(recipe_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Да", callback_data=f"recipes:delete_yes:{recipe_id}"),
                InlineKeyboardButton(text="Нет", callback_data=f"recipes:view:{recipe_id}:0:0"),
            ]
        ]
    )


def cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="recipes:cancel")]]
    )
