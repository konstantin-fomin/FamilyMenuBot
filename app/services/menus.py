from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from app.database import Database
from app.services.ingredients import TASTE_UNIT, normalize_amount


DAY_NAMES = {
    1: "Понедельник",
    2: "Вторник",
    3: "Среда",
    4: "Четверг",
    5: "Пятница",
    6: "Суббота",
    7: "Воскресенье",
}
DAY_SHORT_NAMES = {
    1: "Пн",
    2: "Вт",
    3: "Ср",
    4: "Чт",
    5: "Пт",
    6: "Сб",
    7: "Вс",
}
MONTHS_GENITIVE = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


@dataclass(frozen=True)
class AggregatedIngredient:
    name: str
    amount: float | None
    unit: str


def current_week_start(today: date | None = None) -> date:
    current = today or date.today()
    return current - timedelta(days=current.weekday())


def week_start_by_offset(offset: int, today: date | None = None) -> date:
    return current_week_start(today) + timedelta(days=7 * offset)


def format_week_range(week_start: date) -> str:
    week_end = week_start + timedelta(days=6)
    return f"{_format_date(week_start)} – {_format_date(week_end)}"


async def aggregate_menu_ingredients(db: Database, menu_id: int) -> list[AggregatedIngredient]:
    totals: dict[tuple[str, str], float] = {}
    taste_names: dict[str, AggregatedIngredient] = {}

    for item in await db.list_menu_items(menu_id):
        if item.recipe_id is None:
            continue
        recipe = await db.get_recipe(item.recipe_id)
        if recipe is None:
            continue
        scale = item.count * item.servings / recipe.servings
        for ingredient in await db.list_recipe_ingredients(item.recipe_id):
            name_key = ingredient.name.strip().lower()
            if ingredient.amount is None or ingredient.unit == TASTE_UNIT:
                taste_names[name_key] = AggregatedIngredient(
                    name=ingredient.name,
                    amount=None,
                    unit=TASTE_UNIT,
                )
                continue

            amount, unit = normalize_amount(ingredient.amount, ingredient.unit)
            key = (name_key, unit)
            totals[key] = totals.get(key, 0) + amount * scale

    ingredients = [
        AggregatedIngredient(name=name, amount=round(amount, 2), unit=unit)
        for (name, unit), amount in sorted(totals.items())
    ]
    ingredients.extend(taste_names[name] for name in sorted(taste_names))
    return ingredients


def _format_date(value: date) -> str:
    return f"{value.day} {MONTHS_GENITIVE[value.month]}"
