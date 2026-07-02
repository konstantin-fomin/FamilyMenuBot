from __future__ import annotations

from datetime import date

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.filters import StateFilter
from aiogram.types import CallbackQuery, Message

from app.database import Database, ShoppingItem, User
from app.handlers.common import ACCESS_DENIED_TEXT, require_user
from app.keyboards.shopping import SHOPPING_PAGE_SIZE, clear_bought_confirm_keyboard, shopping_keyboard
from app.services.menus import format_week_range, week_start_by_offset
from app.services.shopping import (
    STATUS_BOUGHT,
    STATUS_HAVE,
    STATUS_TO_BUY,
    add_manual_shopping_items,
    apply_text_status_mark,
    format_shopping_amount,
    next_status,
    rebuild_shopping_list_from_menu,
)
from app.services.telegram import safe_edit_text
from app.states.recipes import Shopping
from app.texts import SHOPPING_BUTTON


router = Router(name="shopping")


@router.message(F.text == SHOPPING_BUTTON)
async def shopping_section(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return
    await state.set_state(Shopping.browsing)
    await state.update_data(offset=0)
    await _send_shopping_list(message, db, 0, 0)


@router.callback_query(F.data.startswith("shop:page:"))
async def shopping_page(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return
    _, _, offset_raw, page_raw = callback.data.split(":")
    await state.set_state(Shopping.browsing)
    await state.update_data(offset=int(offset_raw))
    await _edit_shopping_list(callback, db, int(offset_raw), int(page_raw))


@router.callback_query(F.data.startswith("shop:rebuild:"))
async def shopping_rebuild(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return
    _, _, offset_raw, page_raw = callback.data.split(":")
    offset = int(offset_raw)
    week_start = _week_start(offset)
    await rebuild_shopping_list_from_menu(db, week_start)
    await state.set_state(Shopping.browsing)
    await state.update_data(offset=offset)
    await callback.answer("Список обновлён из меню.")
    await _edit_shopping_list(callback, db, offset, int(page_raw))


@router.callback_query(F.data.startswith("shop:toggle:"))
async def shopping_toggle(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return
    _, _, offset_raw, item_raw, page_raw = callback.data.split(":")
    item = await db.get_shopping_item(int(item_raw))
    if item is None:
        await callback.answer("Позиция уже удалена.", show_alert=True)
        return
    await db.update_shopping_item_status(item.id, next_status(item.status))
    await _edit_shopping_list(callback, db, int(offset_raw), int(page_raw))


@router.callback_query(F.data.startswith("shop:manual:"))
async def shopping_manual_start(callback: CallbackQuery, db: Database, state: FSMContext) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return
    offset = _last_int(callback.data)
    await state.set_state(Shopping.manual)
    await state.update_data(offset=offset)
    await callback.message.answer(
        "Пришлите свои покупки списком, каждая позиция с новой строки.\n\n"
        "Например:\n"
        "кофе 1 шт\n"
        "туалетная бумага"
    )
    await callback.answer()


@router.message(StateFilter(Shopping.manual))
async def shopping_manual_save(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return
    data = await state.get_data()
    offset = int(data.get("offset", 0))
    created = await add_manual_shopping_items(db, _week_start(offset), message.text or "")
    await state.set_state(Shopping.browsing)
    await state.update_data(offset=offset)
    if not created:
        await message.answer(
            "Не увидел позиций. Пришлите список, например:\nкофе 1 шт\nтуалетная бумага"
        )
        return
    await message.answer(f"Добавлено позиций: {len(created)}.")
    await _send_shopping_list(message, db, offset, 0)


@router.message(StateFilter(Shopping.browsing))
async def shopping_text_mark(message: Message, db: Database, state: FSMContext) -> None:
    user = await require_user(message, db)
    if user is None:
        return
    data = await state.get_data()
    offset = int(data.get("offset", 0))
    result = await apply_text_status_mark(db, _week_start(offset), message.text or "")
    if result.status is None:
        await message.answer(
            "Я могу отметить покупки текстом. Например: «есть картошка и лук» или «купил молоко, хлеб»."
        )
        return

    status_text = "есть дома" if result.status == STATUS_HAVE else "куплено"
    parts = []
    if result.marked:
        parts.append(f"Отметил как «{status_text}»: {', '.join(result.marked)}.")
    if result.not_found:
        parts.append(f"Не нашёл в списке: {', '.join(result.not_found)}.")
    await message.answer("\n".join(parts) or "Ничего не изменилось.")
    await _send_shopping_list(message, db, offset, 0)


@router.callback_query(F.data.startswith("shop:clear:"))
async def shopping_clear_prompt(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return
    _, _, offset_raw, page_raw = callback.data.split(":")
    await safe_edit_text(callback.message, 
        "Удалить все позиции со статусом «куплено»?",
        reply_markup=clear_bought_confirm_keyboard(int(offset_raw), int(page_raw)),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("shop:clear_yes:"))
async def shopping_clear_confirm(callback: CallbackQuery, db: Database) -> None:
    user = await _require_callback_user(callback, db)
    if user is None:
        return
    _, _, offset_raw, page_raw = callback.data.split(":")
    deleted = await db.delete_bought_shopping_items(_week_start(int(offset_raw)))
    await callback.answer(f"Удалено: {deleted}")
    await _edit_shopping_list(callback, db, int(offset_raw), int(page_raw))


async def _send_shopping_list(message: Message, db: Database, offset: int, page: int) -> None:
    week_start = _week_start(offset)
    all_items = await db.list_shopping_items(week_start)
    await message.answer(
        _shopping_text(week_start, all_items),
        reply_markup=_shopping_keyboard_for(all_items, offset, page),
    )


async def _edit_shopping_list(callback: CallbackQuery, db: Database, offset: int, page: int) -> None:
    week_start = _week_start(offset)
    all_items = await db.list_shopping_items(week_start)
    await safe_edit_text(callback.message, 
        _shopping_text(week_start, all_items),
        reply_markup=_shopping_keyboard_for(all_items, offset, page),
    )
    await callback.answer()


async def _require_callback_user(callback: CallbackQuery, db: Database) -> User | None:
    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer(ACCESS_DENIED_TEXT, show_alert=True)
    return user


def _shopping_keyboard_for(items: list[ShoppingItem], offset: int, page: int):
    start = page * SHOPPING_PAGE_SIZE
    visible_items = items[start : start + SHOPPING_PAGE_SIZE]
    return shopping_keyboard(visible_items, offset, page, len(items))


def _shopping_text(week_start_raw: str, items: list[ShoppingItem]) -> str:
    week_start = date.fromisoformat(week_start_raw)
    summary = _summary(items)
    lines = [
        f"🛒 <b>Покупки на {format_week_range(week_start)}</b>",
        "",
        f"Купить: {summary[STATUS_TO_BUY]} · Есть: {summary[STATUS_HAVE]} · Куплено: {summary[STATUS_BOUGHT]}",
        "",
    ]
    if not items:
        lines.append("Список пока пуст. Соберите его из меню недели.")
    else:
        lines.append("Нажимайте на продукты, чтобы менять статус.")
    return "\n".join(lines)


def _summary(items: list[ShoppingItem]) -> dict[str, int]:
    return {
        STATUS_TO_BUY: sum(1 for item in items if item.status == STATUS_TO_BUY),
        STATUS_HAVE: sum(1 for item in items if item.status == STATUS_HAVE),
        STATUS_BOUGHT: sum(1 for item in items if item.status == STATUS_BOUGHT),
    }


def _week_start(offset: int) -> str:
    return week_start_by_offset(offset).isoformat()


def _last_int(value: str) -> int:
    return int(value.rsplit(":", maxsplit=1)[-1])
