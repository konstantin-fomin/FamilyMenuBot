from __future__ import annotations

from datetime import date
from html import escape

from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.database import Database, MenuItem, User
from app.handlers.common import ACCESS_DENIED_TEXT, require_user
from app.keyboards.recipes import RECIPES_PAGE_SIZE
from app.keyboards.weekly_menu import (
    day_choice_keyboard,
    edit_menu_items_keyboard,
    menu_item_actions_keyboard,
    move_day_keyboard,
    servings_choice_keyboard,
    weekly_menu_categories_keyboard,
    weekly_menu_keyboard,
    weekly_menu_recipes_keyboard,
)
from app.services.menus import DAY_NAMES, format_week_range, week_start_by_offset
from app.services.telegram import safe_edit_text
from app.texts import WEEKLY_MENU_BUTTON


router = Router(name="weekly_menu")


@router.message(F.text == WEEKLY_MENU_BUTTON)
async def weekly_menu_section(message: Message, db: Database) -> None:
    user = await require_user(message, db)
    if user is None:
        return
    await _send_weekly_menu(message, db, 0)


@router.callback_query(F.data.startswith("wm:home:"))
async def weekly_menu_home(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return
    await _edit_weekly_menu(callback, db, _last_int(callback.data))


@router.callback_query(F.data.startswith("wm:done:"))
async def weekly_menu_done(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return
    await _edit_weekly_menu(callback, db, _last_int(callback.data))


@router.callback_query(F.data.startswith("wm:add:"))
async def weekly_menu_add(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    if await db.recipes_count() == 0:
        await safe_edit_text(callback.message, 
            "Пока нет рецептов, из которых можно составить меню.\n\n"
            "Сначала добавьте рецепт в разделе «📚 Рецепты».",
            reply_markup=weekly_menu_keyboard(_last_int(callback.data)),
        )
        await callback.answer()
        return

    offset = _last_int(callback.data)
    categories = await db.list_categories_with_counts()
    await safe_edit_text(callback.message, 
        "➕ <b>Добавить блюда</b>\n\nСначала выберите категорию рецептов.",
        reply_markup=weekly_menu_categories_keyboard(categories, offset),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wm:cat:"))
async def weekly_menu_category(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    _, _, offset_raw, category_raw, page_raw = callback.data.split(":")
    offset = int(offset_raw)
    category_id = int(category_raw)
    page = int(page_raw)
    total = await db.recipes_count(category_id)
    recipes = await db.list_recipes(
        category_id=category_id,
        limit=RECIPES_PAGE_SIZE,
        offset=page * RECIPES_PAGE_SIZE,
    )
    category = await db.get_category(category_id)
    title = escape(category.name) if category else "Категория"
    text = f"{title}\n\nВыберите рецепт:"
    if not recipes:
        text = f"{title}\n\nВ этой категории пока нет рецептов."

    await safe_edit_text(callback.message, 
        text,
        reply_markup=weekly_menu_recipes_keyboard(recipes, offset, category_id, page, total),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wm:recipe:"))
async def weekly_menu_recipe(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    _, _, offset_raw, recipe_raw, category_raw, page_raw = callback.data.split(":")
    recipe = await db.get_recipe(int(recipe_raw))
    if recipe is None:
        await callback.answer("Рецепт не найден.", show_alert=True)
        return

    await safe_edit_text(callback.message, 
        f"На какой день добавить «{escape(recipe.name)}»?",
        reply_markup=day_choice_keyboard(
            int(offset_raw),
            recipe.id,
            int(category_raw),
            int(page_raw),
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wm:day:"))
async def weekly_menu_choose_day(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    _, _, offset_raw, recipe_raw, day_raw, category_raw, page_raw = callback.data.split(":")
    recipe = await db.get_recipe(int(recipe_raw))
    if recipe is None:
        await callback.answer("Рецепт не найден.", show_alert=True)
        return
    day = _day_from_raw(day_raw)
    await safe_edit_text(
        callback.message,
        f"Сколько порций готовим для «{escape(recipe.name)}»?",
        reply_markup=servings_choice_keyboard(
            int(offset_raw),
            recipe.id,
            day,
            int(category_raw),
            int(page_raw),
            recipe.servings,
        ),
    )
    await callback.answer()


@router.callback_query(F.data == "wm:noop")
async def weekly_menu_noop(callback: CallbackQuery) -> None:
    await callback.answer()


@router.callback_query(F.data.startswith("wm:sv:set:"))
async def weekly_menu_set_servings(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    _, _, _, offset_raw, recipe_raw, day_raw, category_raw, page_raw, servings_raw = callback.data.split(":")
    recipe = await db.get_recipe(int(recipe_raw))
    if recipe is None:
        await callback.answer("Рецепт не найден.", show_alert=True)
        return

    servings = max(int(servings_raw), 1)
    await safe_edit_text(
        callback.message,
        f"Сколько порций готовим для «{escape(recipe.name)}»?",
        reply_markup=servings_choice_keyboard(
            int(offset_raw),
            recipe.id,
            _day_from_raw(day_raw),
            int(category_raw),
            int(page_raw),
            servings,
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wm:sv:add:"))
async def weekly_menu_add_with_servings(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    _, _, _, offset_raw, recipe_raw, day_raw, category_raw, page_raw, servings_raw = callback.data.split(":")
    offset = int(offset_raw)
    day = _day_from_raw(day_raw)
    menu = await _menu_for_offset(db, offset)
    item = await db.add_menu_item(menu.id, int(recipe_raw), day, servings=int(servings_raw))
    day_text = DAY_NAMES[item.day] if item.day else "без дня"
    await callback.answer(
        f"Добавлено: {item.recipe_name}, {day_text}, {item.servings} порц.",
        show_alert=False,
    )

    recipes = await db.list_recipes(
        category_id=int(category_raw),
        limit=RECIPES_PAGE_SIZE,
        offset=int(page_raw) * RECIPES_PAGE_SIZE,
    )
    total = await db.recipes_count(int(category_raw))
    await safe_edit_text(callback.message, 
        "Блюдо добавлено. Можно выбрать ещё рецепт.",
        reply_markup=weekly_menu_recipes_keyboard(
            recipes,
            offset,
            int(category_raw),
            int(page_raw),
            total,
        ),
    )


@router.callback_query(F.data.startswith("wm:edit:"))
async def weekly_menu_edit(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    offset = _last_int(callback.data)
    menu = await _menu_for_offset(db, offset)
    items = await db.list_menu_items(menu.id)
    if not items:
        await safe_edit_text(callback.message, 
            "В меню пока нет блюд для изменения.",
            reply_markup=weekly_menu_keyboard(offset),
        )
        await callback.answer()
        return

    await safe_edit_text(callback.message, 
        "✏️ <b>Изменить меню</b>\n\nВыберите блюдо.",
        reply_markup=edit_menu_items_keyboard(items, offset),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wm:item:"))
async def weekly_menu_item_actions(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    _, _, offset_raw, item_raw = callback.data.split(":")
    item = await db.get_menu_item(int(item_raw))
    if item is None:
        await callback.answer("Блюдо уже убрано из меню.", show_alert=True)
        return

    await safe_edit_text(callback.message, 
        _menu_item_text(item),
        reply_markup=menu_item_actions_keyboard(item.id, int(offset_raw)),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wm:move:"))
async def weekly_menu_move(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    _, _, offset_raw, item_raw = callback.data.split(":")
    item = await db.get_menu_item(int(item_raw))
    if item is None:
        await callback.answer("Блюдо уже убрано из меню.", show_alert=True)
        return

    await safe_edit_text(callback.message, 
        f"Куда перенести «{escape(item.recipe_name)}»?",
        reply_markup=move_day_keyboard(item.id, int(offset_raw)),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("wm:move_day:"))
async def weekly_menu_move_day(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    _, _, offset_raw, item_raw, day_raw = callback.data.split(":")
    await db.move_menu_item(int(item_raw), _day_from_raw(day_raw))
    await callback.answer("День обновлён.")
    await _edit_weekly_menu(callback, db, int(offset_raw))


@router.callback_query(F.data.startswith("wm:dec:"))
async def weekly_menu_decrement(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    _, _, offset_raw, item_raw = callback.data.split(":")
    await db.decrement_menu_item(int(item_raw))
    await callback.answer("Готово.")
    await _edit_weekly_menu(callback, db, int(offset_raw))


@router.callback_query(F.data.startswith("wm:del:"))
async def weekly_menu_delete_item(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return

    _, _, offset_raw, item_raw = callback.data.split(":")
    await db.delete_menu_item(int(item_raw))
    await callback.answer("Блюдо убрано из меню.")
    await _edit_weekly_menu(callback, db, int(offset_raw))


async def _send_weekly_menu(message: Message, db: Database, offset: int) -> None:
    menu = await _menu_for_offset(db, offset)
    items = await db.list_menu_items(menu.id)
    await message.answer(
        _weekly_menu_text(menu.week_start, items),
        reply_markup=weekly_menu_keyboard(offset),
    )


async def _edit_weekly_menu(callback: CallbackQuery, db: Database, offset: int) -> None:
    menu = await _menu_for_offset(db, offset)
    items = await db.list_menu_items(menu.id)
    await safe_edit_text(callback.message, 
        _weekly_menu_text(menu.week_start, items),
        reply_markup=weekly_menu_keyboard(offset),
    )
    await callback.answer()


async def _menu_for_offset(db: Database, offset: int):
    week_start = week_start_by_offset(offset).isoformat()
    return await db.get_or_create_menu(week_start)


async def _require_callback_user(callback: CallbackQuery, db: Database) -> User | None:
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer(ACCESS_DENIED_TEXT, show_alert=True)
    return user


def _weekly_menu_text(week_start_raw: str, items: list[MenuItem]) -> str:
    week_start = date.fromisoformat(week_start_raw)
    lines = [f"📅 <b>Меню на {format_week_range(week_start)}</b>", ""]
    if not items:
        lines.append(
            "Пока меню пустое. Нажмите «➕ Добавить блюда» и выберите рецепты."
        )
        return "\n".join(lines)

    for day in range(1, 8):
        day_items = [item for item in items if item.day == day]
        if not day_items:
            continue
        lines.append(f"<b>{DAY_NAMES[day]}:</b>")
        lines.extend(f"• {_format_menu_item(item)}" for item in day_items)
        lines.append("")

    no_day_items = [item for item in items if item.day is None]
    if no_day_items:
        lines.append("<b>Без дня:</b>")
        lines.extend(f"• {_format_menu_item(item)}" for item in no_day_items)

    return "\n".join(lines).strip()


def _menu_item_text(item: MenuItem) -> str:
    day = DAY_NAMES[item.day] if item.day else "Без дня"
    return (
        f"🍽 <b>{escape(item.recipe_name)}</b>\n"
        f"День: {day}\n"
        f"Порции: {item.servings}\n"
        f"Повторов: {item.count}\n"
        + ("Рецепт удалён из базы, но позицию можно убрать из меню." if item.recipe_id is None else "")
    ).strip()


def _format_menu_item(item: MenuItem) -> str:
    deleted = " (рецепт удалён)" if item.recipe_id is None else ""
    count = f" ×{item.count}" if item.count > 1 else ""
    return f"{escape(item.recipe_name)}{deleted} · 👥 {item.servings} порц.{count}"


def _day_from_raw(value: str) -> int | None:
    day = int(value)
    return day or None


def _last_int(value: str) -> int:
    return int(value.rsplit(":", maxsplit=1)[-1])
