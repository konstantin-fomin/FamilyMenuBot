from datetime import date

import pytest

from app.database import Database
from app.services.menus import aggregate_menu_ingredients, week_start_by_offset


@pytest.fixture
async def db(tmp_path):
    database = Database(tmp_path / "bot.db")
    await database.connect()
    await database.init_schema()
    try:
        yield database
    finally:
        await database.close()


async def _create_recipe(db, name="Борщ", ingredients=None):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    if owner is None:
        owner = await db.get_user_by_telegram_id(1)
    category = (await db.list_categories_with_counts())[0]
    return await db.create_recipe(
        name=name,
        category_id=category.id,
        steps="Готовить до готовности.",
        created_by=owner.id,
        ingredients=ingredients
        or [
            {"name": "картошка", "amount": 500, "unit": "г"},
            {"name": "соль", "amount": None, "unit": "по вкусу"},
        ],
    )


@pytest.mark.asyncio
async def test_create_weekly_menu(db):
    menu = await db.get_or_create_menu("2026-06-29")
    same_menu = await db.get_or_create_menu("2026-06-29")

    assert menu.id == same_menu.id
    assert menu.week_start == "2026-06-29"


@pytest.mark.asyncio
async def test_add_menu_item_repeats_increment_count(db):
    recipe = await _create_recipe(db)
    menu = await db.get_or_create_menu("2026-06-29")

    first = await db.add_menu_item(menu.id, recipe.id, day=1)
    second = await db.add_menu_item(menu.id, recipe.id, day=1)

    assert first.id == second.id
    assert second.count == 2
    assert len(await db.list_menu_items(menu.id)) == 1


@pytest.mark.asyncio
async def test_move_menu_item_day(db):
    recipe = await _create_recipe(db)
    menu = await db.get_or_create_menu("2026-06-29")
    item = await db.add_menu_item(menu.id, recipe.id, day=1)

    moved = await db.move_menu_item(item.id, day=3)

    assert moved.day == 3


@pytest.mark.asyncio
async def test_delete_menu_item(db):
    recipe = await _create_recipe(db)
    menu = await db.get_or_create_menu("2026-06-29")
    item = await db.add_menu_item(menu.id, recipe.id, day=None)

    await db.delete_menu_item(item.id)

    assert await db.list_menu_items(menu.id) == []


def test_week_switching_offsets():
    today = date(2026, 7, 2)

    assert week_start_by_offset(0, today) == date(2026, 6, 29)
    assert week_start_by_offset(1, today) == date(2026, 7, 6)


@pytest.mark.asyncio
async def test_aggregate_menu_ingredients_with_counts_and_units(db):
    recipe = await _create_recipe(
        db,
        ingredients=[
            {"name": "картошка", "amount": 500, "unit": "г"},
            {"name": "картошка", "amount": 1, "unit": "кг"},
            {"name": "лук", "amount": 2, "unit": "шт"},
            {"name": "соль", "amount": None, "unit": "по вкусу"},
        ],
    )
    second_recipe = await _create_recipe(
        db,
        name="Салат",
        ingredients=[
            {"name": "лук", "amount": 1, "unit": "шт"},
            {"name": "соль", "amount": None, "unit": "по вкусу"},
        ],
    )
    menu = await db.get_or_create_menu("2026-06-29")
    await db.add_menu_item(menu.id, recipe.id, day=1, count=2)
    await db.add_menu_item(menu.id, second_recipe.id, day=None)

    ingredients = await aggregate_menu_ingredients(db, menu.id)

    assert [(item.name, item.amount, item.unit) for item in ingredients] == [
        ("картошка", 3000, "г"),
        ("лук", 5, "шт"),
        ("соль", None, "по вкусу"),
    ]


@pytest.mark.asyncio
async def test_deleted_recipe_in_menu_does_not_break(db):
    recipe = await _create_recipe(db)
    menu = await db.get_or_create_menu("2026-06-29")
    item = await db.add_menu_item(menu.id, recipe.id, day=1)

    await db.delete_recipe(recipe.id)

    items = await db.list_menu_items(menu.id)
    assert items[0].id == item.id
    assert items[0].recipe_id is None
    assert items[0].recipe_name == "Борщ"
