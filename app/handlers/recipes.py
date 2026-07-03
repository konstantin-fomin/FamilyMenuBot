from __future__ import annotations

from dataclasses import dataclass
from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message

from app.database import Database, Recipe, User
from app.handlers.common import ACCESS_DENIED_TEXT, require_user
from app.keyboards.recipes import (
    RECIPES_PAGE_SIZE,
    add_recipe_method_keyboard,
    cancel_keyboard,
    categories_keyboard,
    delete_confirm_keyboard,
    edit_photo_keyboard,
    edit_recipe_keyboard,
    ingredients_confirm_keyboard,
    one_message_confirm_keyboard,
    photo_skip_keyboard,
    recipe_card_keyboard,
    recipes_home_keyboard,
    recipes_list_keyboard,
    save_recipe_keyboard,
    search_results_keyboard,
    steps_keyboard,
)
from app.services.ingredients import ParsedIngredient, format_ingredient, parse_ingredients
from app.services.telegram import safe_edit_text
from app.states.recipes import AddRecipe, EditRecipe, RecipeSearch
from app.texts import RECIPES_BUTTON


router = Router(name="recipes")
CANCEL_TEXT = "❌ Отмена"
MAX_RECIPE_NAME_LENGTH = 60
RECIPE_NAME_HINT = "Напишите короткое название рецепта, например: Борщ."
RECIPE_NAME_INPUT_ERROR = (
    "Это похоже на список ингредиентов, а не на название 🙂 "
    "Название нужно короткое, например: Борщ. Попробуйте ещё раз"
)
INGREDIENTS_INPUT_HINT = (
    "Пришлите ингредиенты списком, каждый с новой строки.\n\n"
    "Например:\n"
    "курица 1.5 кг\n"
    "картошка 6 шт\n"
    "соль по вкусу"
)
STEPS_INPUT_HINT = (
    "Пришлите шаги приготовления одним сообщением.\n\n"
    "Например: Нарезать овощи, залить водой и варить 40 минут.\n"
    "Если шаги пока не нужны, нажмите «Пропустить»."
)
ONE_MESSAGE_INPUT_HINT = (
    "Пришлите рецепт одним сообщением:\n\n"
    "первая строка — название\n"
    "дальше — ингредиенты, каждый с новой строки\n"
    "пустая строка отделяет шаги приготовления\n\n"
    "Например:\n"
    "Борщ\n"
    "говядина 500 г\n"
    "картошка 4 шт\n\n"
    "Нарезать овощи и варить до готовности."
)
PHOTO_INPUT_HINT = "Пришлите фото блюда или нажмите «Пропустить»."
PHOTO_CAPTION_LIMIT = 1024


@dataclass(frozen=True)
class OneMessageRecipeDraft:
    name: str
    ingredients: list[ParsedIngredient]
    steps: str


@router.message(F.text == RECIPES_BUTTON)
async def recipes_section(message: Message, db: Database) -> None:
    user = await require_user(message, db)
    if user is None:
        return
    await _send_recipes_home(message, db)


@router.callback_query(F.data == "recipes:home")
async def recipes_home_callback(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return
    categories = await db.list_categories_with_counts()
    await safe_edit_text(callback.message, 
        "📚 <b>Рецепты</b>\n\nВыберите действие или категорию.",
        reply_markup=recipes_home_keyboard(categories),
    )
    await callback.answer()


@router.callback_query(F.data == "recipes:add")
async def start_add_recipe(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    await state.clear()
    await state.set_state(AddRecipe.method)
    await callback.message.answer(
        "➕ <b>Новый рецепт</b>\n\nКак удобнее добавить рецепт?",
        reply_markup=add_recipe_method_keyboard(),
    )
    await callback.answer()


@router.callback_query(StateFilter(AddRecipe.method), F.data == "recipes:add_method:steps")
async def start_add_recipe_by_steps(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    await state.set_state(AddRecipe.name)
    await callback.message.answer(
        f"➕ <b>Новый рецепт</b>\n\n{RECIPE_NAME_HINT}",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.callback_query(StateFilter(AddRecipe.method), F.data == "recipes:add_method:one")
async def start_add_recipe_one_message(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    await state.set_state(AddRecipe.one_message)
    await callback.message.answer(ONE_MESSAGE_INPUT_HINT, reply_markup=cancel_keyboard())
    await callback.answer()


@router.message(StateFilter(AddRecipe.method))
async def add_recipe_method_unexpected(message: Message) -> None:
    await message.answer("Пожалуйста, выберите способ добавления кнопкой ниже.")


@router.message(StateFilter(AddRecipe.one_message))
async def add_recipe_one_message(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    draft, error = parse_one_message_recipe(message.text or "")
    if error:
        await message.answer(error + "\n\n" + ONE_MESSAGE_INPUT_HINT, reply_markup=cancel_keyboard())
        return

    await state.update_data(
        name=draft.name,
        ingredients=_ingredients_to_dicts(draft.ingredients),
        steps=draft.steps,
        photo_file_id=None,
    )
    await state.set_state(AddRecipe.one_category)
    categories = await db.list_categories_with_counts()
    await message.answer(
        "Я понял рецепт так:\n\n"
        + _draft_recipe_card_from_data(
            name=draft.name,
            ingredients=draft.ingredients,
            steps=draft.steps,
            category_name=None,
            photo_file_id=None,
        )
        + "\n\nВыберите категорию рецепта.",
        reply_markup=categories_keyboard(categories, "recipes:add_one_category"),
    )


@router.callback_query(StateFilter(AddRecipe.one_category), F.data.startswith("recipes:add_one_category:"))
async def add_recipe_one_category(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    category_id = _last_int(callback.data)
    category = await db.get_category(category_id)
    if category is None:
        await callback.answer("Категория не найдена.", show_alert=True)
        return

    await state.update_data(category_id=category.id, category_name=category.name)
    await state.set_state(AddRecipe.confirm_save)
    await callback.message.answer(
        await _draft_recipe_card(state),
        reply_markup=one_message_confirm_keyboard(),
    )
    await callback.answer()


@router.callback_query(StateFilter(AddRecipe.confirm_save), F.data == "recipes:add:one_retry")
async def retry_add_recipe_one_message(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddRecipe.one_message)
    await callback.message.answer(
        "Хорошо, пришлите рецепт одним сообщением заново.\n\n" + ONE_MESSAGE_INPUT_HINT,
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(StateFilter(AddRecipe.one_category))
async def add_recipe_one_category_unexpected(message: Message) -> None:
    await message.answer("Пожалуйста, выберите категорию кнопкой ниже. Например: 🍲 Супы.")


@router.message(StateFilter(AddRecipe.name))
async def add_recipe_name(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    name, error = _validate_recipe_name(message.text)
    if error:
        await message.answer(error)
        return

    await state.update_data(name=name)
    await state.set_state(AddRecipe.category)
    categories = await db.list_categories_with_counts()
    await message.answer(
        "Выберите категорию рецепта.",
        reply_markup=categories_keyboard(categories, "recipes:add_category"),
    )


@router.callback_query(StateFilter(AddRecipe.category), F.data.startswith("recipes:add_category:"))
async def add_recipe_category(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    category_id = _last_int(callback.data)
    category = await db.get_category(category_id)
    if category is None:
        await callback.answer("Категория не найдена.", show_alert=True)
        return

    await state.update_data(category_id=category.id, category_name=category.name)
    await state.set_state(AddRecipe.ingredients)
    await callback.message.answer(
        INGREDIENTS_INPUT_HINT,
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(StateFilter(AddRecipe.category))
async def add_recipe_category_unexpected(message: Message) -> None:
    await message.answer("Пожалуйста, выберите категорию кнопкой ниже. Например: 🍲 Супы.")


@router.message(StateFilter(AddRecipe.ingredients))
async def add_recipe_ingredients(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    ingredients = parse_ingredients(message.text or "")
    if not ingredients:
        await message.answer("Не вижу ингредиентов.\n\n" + INGREDIENTS_INPUT_HINT)
        return

    await state.update_data(ingredients=_ingredients_to_dicts(ingredients))
    await state.set_state(AddRecipe.confirm_ingredients)
    await message.answer(
        "Я понял ингредиенты так:\n\n" + _ingredients_preview(ingredients),
        reply_markup=ingredients_confirm_keyboard(),
    )


@router.callback_query(StateFilter(AddRecipe.confirm_ingredients), F.data == "recipes:add:ingredients_retry")
async def retry_add_recipe_ingredients(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddRecipe.ingredients)
    await callback.message.answer(
        "Хорошо, пришлите список ингредиентов заново.\n\n" + INGREDIENTS_INPUT_HINT,
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.callback_query(StateFilter(AddRecipe.confirm_ingredients), F.data == "recipes:add:ingredients_ok")
async def confirm_add_recipe_ingredients(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AddRecipe.steps)
    await callback.message.answer(
        STEPS_INPUT_HINT,
        reply_markup=steps_keyboard(),
    )
    await callback.answer()


@router.message(StateFilter(AddRecipe.confirm_ingredients))
async def add_recipe_confirm_ingredients_unexpected(message: Message) -> None:
    await message.answer(
        "Подтвердите ингредиенты кнопкой «✅ Верно» или исправьте список.\n\n"
        "Если исправляете, пример строки: картошка 6 шт."
    )


@router.callback_query(StateFilter(AddRecipe.steps), F.data == "recipes:add:skip_steps")
async def skip_add_recipe_steps(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(steps="")
    await state.set_state(AddRecipe.photo)
    await callback.message.answer(
        PHOTO_INPUT_HINT,
        reply_markup=photo_skip_keyboard(),
    )
    await callback.answer()


@router.message(StateFilter(AddRecipe.steps))
async def add_recipe_steps(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    await state.update_data(steps=_clean_text(message.text))
    await state.set_state(AddRecipe.photo)
    await message.answer(
        PHOTO_INPUT_HINT,
        reply_markup=photo_skip_keyboard(),
    )


@router.callback_query(StateFilter(AddRecipe.photo), F.data == "recipes:add:skip_photo")
async def skip_add_recipe_photo(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(photo_file_id=None)
    await state.set_state(AddRecipe.confirm_save)
    await callback.message.answer(
        await _draft_recipe_card(state),
        reply_markup=save_recipe_keyboard(),
    )
    await callback.answer()


@router.message(StateFilter(AddRecipe.photo), F.photo)
async def add_recipe_photo(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    await state.update_data(photo_file_id=message.photo[-1].file_id)
    await state.set_state(AddRecipe.confirm_save)
    await message.answer(
        await _draft_recipe_card(state),
        reply_markup=save_recipe_keyboard(),
    )


@router.message(StateFilter(AddRecipe.photo))
async def add_recipe_photo_unexpected(message: Message) -> None:
    await message.answer(PHOTO_INPUT_HINT, reply_markup=photo_skip_keyboard())


@router.callback_query(StateFilter(AddRecipe.confirm_save), F.data == "recipes:add:save")
async def save_new_recipe(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    data = await state.get_data()
    recipe = await db.create_recipe(
        name=data["name"],
        category_id=data["category_id"],
        steps=data.get("steps", ""),
        created_by=user.id,
        ingredients=data["ingredients"],
        photo_file_id=data.get("photo_file_id"),
    )
    await state.clear()
    await _send_recipe_card(
        callback.message,
        recipe,
        recipe_card_keyboard(recipe.id, 0, 0),
        prefix="Рецепт сохранён 💾\n\n",
    )
    await callback.answer()


@router.message(StateFilter(AddRecipe.confirm_save))
async def add_recipe_confirm_save_unexpected(message: Message) -> None:
    await message.answer(
        "Сохраните рецепт кнопкой «💾 Сохранить» или отмените действие.\n\n"
        "Если заметили ошибку, нажмите «✏️ Исправить» или «❌ Отмена»."
    )


@router.callback_query(F.data == "recipes:search")
async def start_recipe_search(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    await state.clear()
    await state.set_state(RecipeSearch.query)
    await callback.message.answer(
        "🔍 <b>Поиск рецептов</b>\n\nНапишите часть названия рецепта.",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


@router.message(StateFilter(RecipeSearch.query))
async def recipe_search_query(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    query = _clean_text(message.text)
    if not query:
        await message.answer("Напишите, что искать. Например: суп или курица.")
        return

    await state.update_data(query=query)
    await _send_search_results(message, db, query, 0)


@router.callback_query(F.data.startswith("recipes:search_page:"))
async def recipe_search_page(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    query = (await state.get_data()).get("query")
    if not query:
        await callback.message.answer(
            "Поисковый запрос потерялся. Нажмите «🔍 Поиск» и попробуйте ещё раз."
        )
        await callback.answer()
        return

    page = max(_last_int(callback.data), 0)
    await _edit_search_results(callback, db, query, page)


@router.callback_query(F.data.startswith("recipes:list:"))
async def recipes_list(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    _, _, category_raw, page_raw = callback.data.split(":")
    category_id = int(category_raw)
    page = max(int(page_raw), 0)
    category_filter = category_id or None
    total = await db.recipes_count(category_filter)
    recipes = await db.list_recipes(
        category_id=category_filter,
        limit=RECIPES_PAGE_SIZE,
        offset=page * RECIPES_PAGE_SIZE,
    )

    title = "📖 <b>Все рецепты</b>"
    if category_filter is not None:
        category = await db.get_category(category_filter)
        title = f"{escape(category.name)}" if category else title

    if not recipes:
        text = f"{title}\n\nПока здесь нет рецептов."
    else:
        text = f"{title}\n\nВыберите рецепт:"

    await safe_edit_text(callback.message, 
        text,
        reply_markup=recipes_list_keyboard(recipes, category_id, page, total),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("recipes:view:"))
async def view_recipe(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    _, _, recipe_raw, category_raw, page_raw = callback.data.split(":")
    await _show_recipe_card(callback, db, int(recipe_raw), int(category_raw), int(page_raw))


@router.callback_query(F.data.startswith("recipes:edit:"))
async def edit_recipe(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    recipe_id = _last_int(callback.data)
    recipe = await db.get_recipe(recipe_id)
    if recipe is None:
        await callback.answer("Рецепт не найден.", show_alert=True)
        return

    await safe_edit_text(callback.message, 
        f"✏️ Что изменить в рецепте «{escape(recipe.name)}»?",
        reply_markup=edit_recipe_keyboard(recipe.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("recipes:edit_field:"))
async def choose_recipe_edit_field(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    _, _, recipe_raw, field = callback.data.split(":")
    recipe_id = int(recipe_raw)
    recipe = await db.get_recipe(recipe_id)
    if recipe is None:
        await callback.answer("Рецепт не найден.", show_alert=True)
        return

    await state.update_data(recipe_id=recipe_id)
    prompts: dict[str, tuple[State, str]] = {
        "name": (EditRecipe.name, "Напишите новое короткое название. Например: Борщ."),
        "ingredients": (
            EditRecipe.ingredients,
            "Пришлите новый список ингредиентов целиком.\n\n" + INGREDIENTS_INPUT_HINT,
        ),
        "steps": (EditRecipe.steps, STEPS_INPUT_HINT),
        "photo": (
            EditRecipe.photo,
            "Пришлите новое фото блюда. Если фото больше не нужно, нажмите «Удалить фото».",
        ),
    }
    if field == "category":
        await state.set_state(EditRecipe.category)
        categories = await db.list_categories_with_counts()
        await callback.message.answer(
            "Выберите новую категорию. Например: 🍲 Супы.",
            reply_markup=categories_keyboard(categories, "recipes:edit_category"),
        )
    elif field == "photo":
        await state.set_state(EditRecipe.photo)
        await callback.message.answer(
            prompts[field][1],
            reply_markup=edit_photo_keyboard(recipe.id, bool(recipe.photo_file_id)),
        )
    elif field in prompts:
        next_state, prompt = prompts[field]
        await state.set_state(next_state)
        await callback.message.answer(prompt, reply_markup=cancel_keyboard())
    else:
        await callback.answer("Неизвестное поле.", show_alert=True)
        return
    await callback.answer()


@router.message(StateFilter(EditRecipe.name))
async def edit_recipe_name(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    name, error = _validate_recipe_name(message.text)
    if error:
        await message.answer(error)
        return

    recipe_id = (await state.get_data())["recipe_id"]
    await db.update_recipe_name(recipe_id, name)
    await _finish_edit(message, db, state, recipe_id)


@router.callback_query(StateFilter(EditRecipe.category), F.data.startswith("recipes:edit_category:"))
async def edit_recipe_category(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    category_id = _last_int(callback.data)
    category = await db.get_category(category_id)
    if category is None:
        await callback.answer("Категория не найдена.", show_alert=True)
        return

    recipe_id = (await state.get_data())["recipe_id"]
    await db.update_recipe_category(recipe_id, category.id)
    await state.clear()
    await safe_edit_text(callback.message, "Категория обновлена.")
    await _show_recipe_card(callback, db, recipe_id, 0, 0)


@router.message(StateFilter(EditRecipe.category))
async def edit_recipe_category_unexpected(message: Message) -> None:
    await message.answer("Пожалуйста, выберите категорию кнопкой ниже. Например: 🍲 Супы.")


@router.message(StateFilter(EditRecipe.ingredients))
async def edit_recipe_ingredients(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    ingredients = parse_ingredients(message.text or "")
    if not ingredients:
        await message.answer("Не вижу ингредиентов.\n\n" + INGREDIENTS_INPUT_HINT)
        return

    recipe_id = (await state.get_data())["recipe_id"]
    await db.update_recipe_ingredients(recipe_id, _ingredients_to_dicts(ingredients))
    await _finish_edit(message, db, state, recipe_id)


@router.message(StateFilter(EditRecipe.steps))
async def edit_recipe_steps(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    recipe_id = (await state.get_data())["recipe_id"]
    await db.update_recipe_steps(recipe_id, _clean_text(message.text))
    await _finish_edit(message, db, state, recipe_id)


@router.message(StateFilter(EditRecipe.photo), F.photo)
async def edit_recipe_photo(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    recipe_id = (await state.get_data())["recipe_id"]
    await db.update_recipe_photo(recipe_id, message.photo[-1].file_id)
    await _finish_edit(message, db, state, recipe_id)


@router.message(StateFilter(EditRecipe.photo))
async def edit_recipe_photo_unexpected(message: Message) -> None:
    await message.answer("Пришлите фото блюда или отмените действие.")


@router.callback_query(F.data.startswith("recipes:edit_photo_delete:"))
async def delete_recipe_photo(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    recipe_id = _last_int(callback.data)
    recipe = await db.get_recipe(recipe_id)
    if recipe is None:
        await callback.answer("Рецепт не найден.", show_alert=True)
        return

    await db.update_recipe_photo(recipe_id, None)
    await state.clear()
    await callback.message.answer("Фото удалено.")
    await _show_recipe_card(callback, db, recipe_id, 0, 0)


@router.callback_query(F.data.startswith("recipes:delete:"))
async def delete_recipe_prompt(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    recipe_id = _last_int(callback.data)
    recipe = await db.get_recipe(recipe_id)
    if recipe is None:
        await callback.answer("Рецепт не найден.", show_alert=True)
        return

    await safe_edit_text(callback.message, 
        f"Точно удалить «{escape(recipe.name)}»?",
        reply_markup=delete_confirm_keyboard(recipe.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("recipes:delete_yes:"))
async def delete_recipe_confirm(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    recipe_id = _last_int(callback.data)
    recipe = await db.get_recipe(recipe_id)
    await db.delete_recipe(recipe_id)
    name = recipe.name if recipe else "Рецепт"
    await safe_edit_text(callback.message, 
        f"«{escape(name)}» удалён.",
        reply_markup=recipes_home_keyboard(await db.list_categories_with_counts()),
    )
    await callback.answer()


@router.callback_query(F.data == "recipes:cancel")
async def cancel_recipe_dialog(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Действие отменено.")
    await callback.answer()


@router.message(StateFilter(AddRecipe, EditRecipe, RecipeSearch), F.text == CANCEL_TEXT)
async def cancel_recipe_dialog_by_text(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.")


async def _send_recipes_home(message: Message, db: Database) -> None:
    categories = await db.list_categories_with_counts()
    await message.answer(
        "📚 <b>Рецепты</b>\n\nВыберите действие или категорию.",
        reply_markup=recipes_home_keyboard(categories),
    )


async def _require_callback_user(callback: CallbackQuery, db: Database) -> User | None:
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer(ACCESS_DENIED_TEXT, show_alert=True)
    return user


async def _send_search_results(message: Message, db: Database, query: str, page: int) -> None:
    total = await db.search_recipes_count(query)
    recipes = await db.search_recipes(
        query,
        limit=RECIPES_PAGE_SIZE,
        offset=page * RECIPES_PAGE_SIZE,
    )
    await message.answer(
        _search_results_text(query, total),
        reply_markup=search_results_keyboard(recipes, page, total),
    )


async def _edit_search_results(
    callback: CallbackQuery,
    db: Database,
    query: str,
    page: int,
) -> None:
    total = await db.search_recipes_count(query)
    recipes = await db.search_recipes(
        query,
        limit=RECIPES_PAGE_SIZE,
        offset=page * RECIPES_PAGE_SIZE,
    )
    await safe_edit_text(
        callback.message,
        _search_results_text(query, total),
        reply_markup=search_results_keyboard(recipes, page, total),
    )
    await callback.answer()


def _search_results_text(query: str, total: int) -> str:
    escaped_query = escape(query)
    if total == 0:
        return (
            f"🔍 <b>Поиск:</b> {escaped_query}\n\n"
            "Ничего не нашлось. Можно попробовать другое слово или посмотреть все рецепты."
        )
    return f"🔍 <b>Поиск:</b> {escaped_query}\n\nВыберите рецепт:"


async def _show_recipe_card(
    callback: CallbackQuery,
    db: Database,
    recipe_id: int,
    category_id: int,
    page: int,
) -> None:
    recipe = await db.get_recipe(recipe_id)
    if recipe is None:
        await callback.answer("Рецепт не найден.", show_alert=True)
        return

    await _send_recipe_card(
        callback.message,
        recipe,
        recipe_card_keyboard(recipe.id, category_id, page),
    )
    await callback.answer()


async def _finish_edit(message: Message, db: Database, state: FSMContext, recipe_id: int) -> None:
    await state.clear()
    recipe = await db.get_recipe(recipe_id)
    if recipe is None:
        await message.answer("Рецепт не найден.")
        return
    await _send_recipe_card(
        message,
        recipe,
        recipe_card_keyboard(recipe.id, 0, 0),
        prefix="Готово, рецепт обновлён.\n\n",
    )


async def _send_recipe_card(
    message: Message,
    recipe: Recipe,
    reply_markup,
    prefix: str = "",
) -> None:
    text = prefix + _recipe_card_text(recipe)
    if not recipe.photo_file_id:
        await message.answer(text, reply_markup=reply_markup)
        return

    if len(text) <= PHOTO_CAPTION_LIMIT:
        await message.answer_photo(
            photo=recipe.photo_file_id,
            caption=text,
            reply_markup=reply_markup,
        )
        return

    await message.answer_photo(photo=recipe.photo_file_id)
    await message.answer(text, reply_markup=reply_markup)


async def _draft_recipe_card(state: FSMContext) -> str:
    data = await state.get_data()
    ingredients = [
        ParsedIngredient(
            name=item["name"],
            amount=item.get("amount"),
            unit=item["unit"],
        )
        for item in data["ingredients"]
    ]
    return _draft_recipe_card_from_data(
        name=data["name"],
        ingredients=ingredients,
        steps=data.get("steps", ""),
        category_name=data.get("category_name"),
        photo_file_id=data.get("photo_file_id"),
    )


def _draft_recipe_card_from_data(
    name: str,
    ingredients: list[ParsedIngredient],
    steps: str,
    category_name: str | None,
    photo_file_id: str | None,
) -> str:
    lines = [
        "Проверьте рецепт перед сохранением:",
        "",
        f"🍽 <b>{escape(name)}</b>",
    ]
    if category_name:
        lines.append(f"Категория: {escape(category_name)}")
    lines.extend([
        f"Фото: {'добавлено' if photo_file_id else 'не добавлено'}",
        "",
        "<b>Ингредиенты:</b>",
        _ingredients_preview(ingredients),
        "",
        "<b>Шаги:</b>",
        escape(steps or "Не указаны"),
    ])
    return "\n".join(lines)


def _recipe_card_text(recipe: Recipe) -> str:
    lines = [
        f"🍽 <b>{escape(recipe.name)}</b>",
        f"Категория: {escape(recipe.category_name)}",
        "",
        "<b>Ингредиенты:</b>",
    ]
    if recipe.ingredients:
        lines.extend(
            f"• {escape(format_ingredient(item.name, item.amount, item.unit))}"
            for item in recipe.ingredients
        )
    else:
        lines.append("Не указаны")
    lines.extend(["", "<b>Шаги:</b>", escape(recipe.steps or "Не указаны")])
    return "\n".join(lines)


def _ingredients_preview(ingredients: list[ParsedIngredient]) -> str:
    return "\n".join(
        f"• {escape(format_ingredient(item.name, item.amount, item.unit))}"
        for item in ingredients
    )


def _ingredients_to_dicts(ingredients: list[ParsedIngredient]) -> list[dict]:
    return [
        {"name": item.name, "amount": item.amount, "unit": item.unit}
        for item in ingredients
    ]


def _clean_text(text: str | None) -> str:
    return " ".join((text or "").strip().split())


def parse_one_message_recipe(text: str) -> tuple[OneMessageRecipeDraft | None, str | None]:
    raw_lines = text.strip().splitlines()
    if not raw_lines:
        return None, "Не вижу рецепт. Первая строка должна быть названием."

    name = _clean_text(raw_lines[0])
    if not name:
        return None, "Первая строка должна быть названием рецепта."
    if len(name) > MAX_RECIPE_NAME_LENGTH:
        return None, "Название должно быть не длиннее 60 символов."

    body_lines = raw_lines[1:]
    separator_index = next(
        (index for index, line in enumerate(body_lines) if not line.strip()),
        None,
    )
    if separator_index is None:
        ingredient_lines = body_lines
        step_lines: list[str] = []
    else:
        ingredient_lines = body_lines[:separator_index]
        step_lines = body_lines[separator_index + 1 :]

    ingredients = parse_ingredients("\n".join(ingredient_lines))
    if not ingredients:
        return None, "Нужен хотя бы один ингредиент."

    steps = "\n".join(line.strip() for line in step_lines).strip()
    return OneMessageRecipeDraft(name=name, ingredients=ingredients, steps=steps), None


def _validate_recipe_name(text: str | None) -> tuple[str | None, str | None]:
    raw_text = text or ""
    name = _clean_text(raw_text)
    if not name:
        return None, "Название не должно быть пустым. " + RECIPE_NAME_HINT
    if "\n" in raw_text.strip() or len(name) > MAX_RECIPE_NAME_LENGTH:
        return None, RECIPE_NAME_INPUT_ERROR
    return name, None


def _last_int(value: str) -> int:
    return int(value.rsplit(":", maxsplit=1)[-1])
