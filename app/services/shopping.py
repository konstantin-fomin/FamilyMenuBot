from __future__ import annotations

from dataclasses import dataclass
import re

from app.database import Database, ShoppingItem
from app.services.ingredients import TASTE_UNIT, ParsedIngredient, normalize_amount, parse_ingredients


STATUS_TO_BUY = "to_buy"
STATUS_HAVE = "have"
STATUS_BOUGHT = "bought"
STATUS_ORDER = (STATUS_TO_BUY, STATUS_BOUGHT, STATUS_HAVE)


@dataclass(frozen=True)
class ShoppingBuildItem:
    name: str
    amount: float | None
    unit: str
    recipe_names: str


@dataclass(frozen=True)
class TextMarkResult:
    status: str | None
    marked: list[str]
    not_found: list[str]


async def rebuild_shopping_list_from_menu(db: Database, week_start: str) -> None:
    menu = await db.get_menu_by_week_start(week_start)
    built_items = await build_shopping_items_from_menu(db, menu.id) if menu else []
    existing_items = await db.list_shopping_items(week_start)
    menu_items_by_name = {
        normalize_product_name(item.name): item
        for item in existing_items
        if item.source == "menu"
    }

    keep_ids = []
    for position, built_item in enumerate(built_items, start=1):
        key = normalize_product_name(built_item.name)
        existing = menu_items_by_name.get(key)
        if existing is None:
            created = await db.create_shopping_item(
                week_start=week_start,
                name=built_item.name,
                amount=built_item.amount,
                unit=built_item.unit,
                status=STATUS_TO_BUY,
                source="menu",
                recipe_names=built_item.recipe_names,
                position=position,
            )
            keep_ids.append(created.id)
        else:
            await db.update_shopping_menu_item(
                existing.id,
                built_item.name,
                built_item.amount,
                built_item.unit,
                built_item.recipe_names,
            )
            keep_ids.append(existing.id)

    await db.delete_missing_menu_shopping_items(week_start, keep_ids)


async def build_shopping_items_from_menu(db: Database, menu_id: int) -> list[ShoppingBuildItem]:
    totals: dict[tuple[str, str], float] = {}
    display_names: dict[tuple[str, str], str] = {}
    recipe_names: dict[tuple[str, str], set[str]] = {}
    taste_items: dict[str, tuple[str, set[str]]] = {}

    for menu_item in await db.list_menu_items(menu_id):
        if menu_item.recipe_id is None:
            continue
        for ingredient in await db.list_recipe_ingredients(menu_item.recipe_id):
            name_key = normalize_product_name(ingredient.name)
            if ingredient.amount is None or ingredient.unit == TASTE_UNIT:
                item_name, recipes = taste_items.get(name_key, (ingredient.name, set()))
                recipes.add(menu_item.recipe_name)
                taste_items[name_key] = (item_name, recipes)
                continue

            amount, unit = normalize_amount(ingredient.amount, ingredient.unit)
            key = (name_key, unit)
            totals[key] = totals.get(key, 0) + amount * menu_item.count
            display_names.setdefault(key, ingredient.name)
            recipe_names.setdefault(key, set()).add(menu_item.recipe_name)

    items = [
        ShoppingBuildItem(
            name=display_names[key],
            amount=amount,
            unit=key[1],
            recipe_names=", ".join(sorted(recipe_names[key])),
        )
        for key, amount in sorted(totals.items())
    ]
    items.extend(
        ShoppingBuildItem(
            name=item_name,
            amount=None,
            unit=TASTE_UNIT,
            recipe_names=", ".join(sorted(recipes)),
        )
        for _, (item_name, recipes) in sorted(taste_items.items())
    )
    return items


async def add_manual_shopping_items(db: Database, week_start: str, text: str) -> list[ShoppingItem]:
    created = []
    for ingredient in parse_ingredients(text):
        item = await db.create_shopping_item(
            week_start=week_start,
            name=ingredient.name,
            amount=ingredient.amount,
            unit=ingredient.unit,
            status=STATUS_TO_BUY,
            source="manual",
        )
        created.append(item)
    return created


async def apply_text_status_mark(db: Database, week_start: str, text: str) -> TextMarkResult:
    status, names = parse_status_text(text)
    if status is None:
        return TextMarkResult(status=None, marked=[], not_found=[])

    items = await db.list_shopping_items(week_start)
    items_by_name: dict[str, list[ShoppingItem]] = {}
    for item in items:
        items_by_name.setdefault(normalize_product_name(item.name), []).append(item)

    marked = []
    not_found = []
    for name in names:
        key = normalize_product_name(name)
        matched_items = items_by_name.get(key) or _find_by_simple_form(items_by_name, key)
        if not matched_items:
            not_found.append(name)
            continue
        for item in matched_items:
            await db.update_shopping_item_status(item.id, status)
        marked.append(name)

    return TextMarkResult(status=status, marked=marked, not_found=not_found)


def parse_status_text(text: str) -> tuple[str | None, list[str]]:
    cleaned = text.strip().lower()
    status = None
    marker = None
    if cleaned.startswith(("есть ", "есть:")):
        status = STATUS_HAVE
        marker = re.sub(r"^есть[:\s]+", "", cleaned)
    elif cleaned.startswith(("купил ", "купила ", "купили ", "куплено ")):
        status = STATUS_BOUGHT
        marker = re.sub(r"^(купил|купила|купили|куплено)[:\s]+", "", cleaned)
    if status is None or not marker:
        return None, []

    marker = marker.replace(" и ", ",")
    names = [part.strip(" .!?,;:") for part in marker.split(",")]
    return status, [name for name in names if name]


def next_status(status: str) -> str:
    if status == STATUS_TO_BUY:
        return STATUS_BOUGHT
    if status == STATUS_BOUGHT:
        return STATUS_HAVE
    return STATUS_TO_BUY


def format_shopping_amount(amount: float | None, unit: str) -> str:
    if amount is None or unit == TASTE_UNIT:
        return TASTE_UNIT
    display_amount = float(amount)
    display_unit = unit
    if unit == "г" and display_amount >= 1000:
        display_amount /= 1000
        display_unit = "кг"
    elif unit == "мл" and display_amount >= 1000:
        display_amount /= 1000
        display_unit = "л"
    return f"{_format_number(display_amount)} {display_unit}"


def shopping_item_button_text(item: ShoppingItem) -> str:
    icons = {
        STATUS_TO_BUY: "🔲",
        STATUS_HAVE: "🏠",
        STATUS_BOUGHT: "✅",
    }
    return f"{icons[item.status]} {item.name} — {format_shopping_amount(item.amount, item.unit)}"


def normalize_product_name(name: str) -> str:
    value = name.strip().lower().replace("ё", "е")
    value = re.sub(r"[^а-яa-z0-9\s-]", "", value)
    value = " ".join(value.split())
    if value.endswith("ки"):
        value = value[:-2] + "ка"
    elif value.endswith("ки "):
        value = value[:-3] + "ка"
    return value


def _find_by_simple_form(items_by_name: dict[str, list[ShoppingItem]], key: str) -> list[ShoppingItem]:
    variants = {key}
    if key.endswith("а"):
        variants.add(key[:-1] + "ы")
        variants.add(key[:-1] + "и")
    if key.endswith("ы") or key.endswith("и"):
        variants.add(key[:-1] + "а")
    for variant in variants:
        if variant in items_by_name:
            return items_by_name[variant]
    return []


def _format_number(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return f"{value:g}"
