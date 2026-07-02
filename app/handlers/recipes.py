from __future__ import annotations

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
    cancel_keyboard,
    categories_keyboard,
    delete_confirm_keyboard,
    edit_recipe_keyboard,
    ingredients_confirm_keyboard,
    recipe_card_keyboard,
    recipes_home_keyboard,
    recipes_list_keyboard,
    save_recipe_keyboard,
    steps_keyboard,
)
from app.services.ingredients import ParsedIngredient, format_ingredient, parse_ingredients
from app.states.recipes import AddRecipe, EditRecipe
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
    await callback.message.edit_text(
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
    await state.set_state(AddRecipe.name)
    await callback.message.answer(
        f"➕ <b>Новый рецепт</b>\n\n{RECIPE_NAME_HINT}",
        reply_markup=cancel_keyboard(),
    )
    await callback.answer()


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
    await state.set_state(AddRecipe.confirm_save)
    await callback.message.answer(
        await _draft_recipe_card(state),
        reply_markup=save_recipe_keyboard(),
    )
    await callback.answer()


@router.message(StateFilter(AddRecipe.steps))
async def add_recipe_steps(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    await state.update_data(steps=_clean_text(message.text))
    await state.set_state(AddRecipe.confirm_save)
    await message.answer(
        await _draft_recipe_card(state),
        reply_markup=save_recipe_keyboard(),
    )


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
    )
    await state.clear()
    await callback.message.edit_text(
        "Рецепт сохранён 💾\n\n" + _recipe_card_text(recipe),
        reply_markup=recipe_card_keyboard(recipe.id, 0, 0),
    )
    await callback.answer()


@router.message(StateFilter(AddRecipe.confirm_save))
async def add_recipe_confirm_save_unexpected(message: Message) -> None:
    await message.answer(
        "Сохраните рецепт кнопкой «💾 Сохранить» или отмените действие.\n\n"
        "Если заметили ошибку, нажмите «❌ Отмена» и добавьте рецепт заново."
    )


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

    await callback.message.edit_text(
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

    await callback.message.edit_text(
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
    }
    if field == "category":
        await state.set_state(EditRecipe.category)
        categories = await db.list_categories_with_counts()
        await callback.message.answer(
            "Выберите новую категорию. Например: 🍲 Супы.",
            reply_markup=categories_keyboard(categories, "recipes:edit_category"),
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
    await callback.message.edit_text("Категория обновлена.")
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

    await callback.message.edit_text(
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
    await callback.message.edit_text(
        f"«{escape(name)}» удалён.",
        reply_markup=recipes_home_keyboard(await db.list_categories_with_counts()),
    )
    await callback.answer()


@router.callback_query(F.data == "recipes:cancel")
async def cancel_recipe_dialog(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.answer("Действие отменено.")
    await callback.answer()


@router.message(StateFilter(AddRecipe, EditRecipe), F.text == CANCEL_TEXT)
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

    await callback.message.edit_text(
        _recipe_card_text(recipe),
        reply_markup=recipe_card_keyboard(recipe.id, category_id, page),
    )
    await callback.answer()


async def _finish_edit(message: Message, db: Database, state: FSMContext, recipe_id: int) -> None:
    await state.clear()
    recipe = await db.get_recipe(recipe_id)
    await message.answer(
        "Готово, рецепт обновлён.\n\n" + _recipe_card_text(recipe),
        reply_markup=recipe_card_keyboard(recipe.id, 0, 0),
    )


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
    lines = [
        "Проверьте рецепт перед сохранением:",
        "",
        f"🍽 <b>{escape(data['name'])}</b>",
        f"Категория: {escape(data['category_name'])}",
        "",
        "<b>Ингредиенты:</b>",
        _ingredients_preview(ingredients),
        "",
        "<b>Шаги:</b>",
        escape(data.get("steps") or "Не указаны"),
    ]
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
