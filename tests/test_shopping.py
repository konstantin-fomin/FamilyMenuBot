import pytest

from app.database import Database
from app.services.departments import detect_department_name, normalize_product_name, resolve_department
from app.services.shopping import (
    STATUS_BOUGHT,
    STATUS_HAVE,
    STATUS_TO_BUY,
    add_manual_shopping_items,
    apply_text_status_mark,
    format_shopping_amount,
    rebuild_shopping_list_from_menu,
)


@pytest.fixture
async def db(tmp_path):
    database = Database(tmp_path / "bot.db")
    await database.connect()
    await database.init_schema()
    try:
        yield database
    finally:
        await database.close()


async def _owner(db):
    user = await db.create_owner_if_first(telegram_id=1, name="Анна")
    return user or await db.get_user_by_telegram_id(1)


async def _recipe(db, name, ingredients, servings=4):
    user = await _owner(db)
    category = (await db.list_categories_with_counts())[0]
    return await db.create_recipe(
        name=name,
        category_id=category.id,
        steps="",
        created_by=user.id,
        ingredients=ingredients,
        servings=servings,
    )


@pytest.mark.asyncio
async def test_generate_shopping_list_from_menu_with_sums(db):
    soup = await _recipe(
        db,
        "Борщ",
        [
            {"name": "картошка", "amount": 500, "unit": "г"},
            {"name": "молоко", "amount": 1, "unit": "л"},
            {"name": "соль", "amount": None, "unit": "по вкусу"},
        ],
    )
    salad = await _recipe(
        db,
        "Салат",
        [
            {"name": "картошка", "amount": 1, "unit": "кг"},
            {"name": "молоко", "amount": 500, "unit": "мл"},
        ],
    )
    menu = await db.get_or_create_menu("2026-06-29")
    await db.add_menu_item(menu.id, soup.id, day=1, count=2)
    await db.add_menu_item(menu.id, salad.id, day=None)

    await rebuild_shopping_list_from_menu(db, "2026-06-29")

    items = await db.list_shopping_items("2026-06-29")
    by_name = {item.name: item for item in items}
    assert by_name["картошка"].amount == 2000
    assert by_name["картошка"].unit == "г"
    assert by_name["молоко"].amount == 2500
    assert by_name["молоко"].unit == "мл"
    assert by_name["соль"].amount is None
    assert by_name["соль"].unit == "по вкусу"
    assert by_name["картошка"].recipe_names == "Борщ, Салат"


@pytest.mark.asyncio
async def test_generate_shopping_list_scales_recipe_servings_fractionally(db):
    recipe = await _recipe(
        db,
        "Паста",
        [
            {"name": "макароны", "amount": 400, "unit": "г"},
            {"name": "сыр", "amount": 120, "unit": "г"},
            {"name": "соль", "amount": None, "unit": "по вкусу"},
        ],
        servings=4,
    )
    menu = await db.get_or_create_menu("2026-06-29")
    await db.add_menu_item(menu.id, recipe.id, day=1, servings=6)

    await rebuild_shopping_list_from_menu(db, "2026-06-29")

    items = await db.list_shopping_items("2026-06-29")
    by_name = {item.name: item for item in items}
    assert by_name["макароны"].amount == 600
    assert by_name["сыр"].amount == 180
    assert by_name["соль"].amount is None


@pytest.mark.asyncio
async def test_rebuild_preserves_statuses_and_manual_items(db):
    recipe = await _recipe(
        db,
        "Борщ",
        [
            {"name": "картошка", "amount": 500, "unit": "г"},
            {"name": "лук", "amount": 1, "unit": "шт"},
        ],
    )
    menu = await db.get_or_create_menu("2026-06-29")
    await db.add_menu_item(menu.id, recipe.id, day=1)
    await rebuild_shopping_list_from_menu(db, "2026-06-29")
    potato = next(item for item in await db.list_shopping_items("2026-06-29") if item.name == "картошка")
    await db.update_shopping_item_status(potato.id, STATUS_BOUGHT)
    manual = await db.create_shopping_item(
        week_start="2026-06-29",
        name="кофе",
        amount=1,
        unit="шт",
        source="manual",
    )

    await db.update_recipe_ingredients(
        recipe.id,
        [{"name": "картошка", "amount": 1, "unit": "кг"}],
    )
    await rebuild_shopping_list_from_menu(db, "2026-06-29")

    items = await db.list_shopping_items("2026-06-29")
    by_name = {item.name: item for item in items}
    assert by_name["картошка"].status == STATUS_BOUGHT
    assert by_name["картошка"].amount == 1000
    assert "лук" not in by_name
    assert by_name["кофе"].id == manual.id
    assert by_name["кофе"].source == "manual"


@pytest.mark.asyncio
async def test_manual_items_parse_free_form_lines(db):
    created = await add_manual_shopping_items(
        db,
        "2026-06-29",
        "кофе 1 шт\nтуалетная бумага",
    )

    assert [(item.name, item.amount, item.unit, item.source) for item in created] == [
        ("кофе", 1, "шт", "manual"),
        ("туалетная бумага", None, "по вкусу", "manual"),
    ]


@pytest.mark.asyncio
async def test_text_status_recognition_marks_found_and_not_found(db):
    await db.create_shopping_item("2026-06-29", "картошка", 500, "г")
    await db.create_shopping_item("2026-06-29", "лук", 1, "шт")

    result = await apply_text_status_mark(db, "2026-06-29", "есть картошки и хлеб")

    items = await db.list_shopping_items("2026-06-29")
    by_name = {item.name: item for item in items}
    assert result.status == STATUS_HAVE
    assert result.marked == ["картошки"]
    assert result.not_found == ["хлеб"]
    assert by_name["картошка"].status == STATUS_HAVE
    assert by_name["лук"].status == STATUS_TO_BUY


@pytest.mark.asyncio
async def test_text_status_recognition_bought(db):
    await db.create_shopping_item("2026-06-29", "молоко", 1000, "мл")
    await db.create_shopping_item("2026-06-29", "хлеб", 1, "шт")

    result = await apply_text_status_mark(db, "2026-06-29", "купил молоко, хлеб")

    assert result.status == STATUS_BOUGHT
    assert result.marked == ["молоко", "хлеб"]
    assert all(item.status == STATUS_BOUGHT for item in await db.list_shopping_items("2026-06-29"))


@pytest.mark.parametrize(
    ("amount", "unit", "expected"),
    [
        (2500, "г", "2.5 кг"),
        (1500, "мл", "1.5 л"),
        (1333.333, "г", "1.33 кг"),
        (6, "шт", "6 шт"),
        (None, "по вкусу", "по вкусу"),
    ],
)
def test_pretty_amount_format(amount, unit, expected):
    assert format_shopping_amount(amount, unit) == expected


@pytest.mark.parametrize(
    ("product_name", "department_name"),
    [
        ("картошка", "🥬 Овощи и фрукты"),
        ("моркови", "🥬 Овощи и фрукты"),
        ("куриное филе", "🥩 Мясо и рыба"),
        ("творог", "🥛 Молочное и яйца"),
        ("макароны", "🥫 Бакалея"),
        ("батон", "🍞 Хлеб и выпечка"),
        ("пельмени", "🧊 Заморозка"),
        ("туалетная бумага", "🧴 Бытовое"),
        ("что-то редкое", "📦 Прочее"),
    ],
)
def test_detect_department_by_product_name(product_name, department_name):
    assert detect_department_name(product_name) == department_name


@pytest.mark.asyncio
async def test_manual_department_override_has_priority_over_dictionary(db):
    departments = await db.list_shopping_departments()
    grocery = next(department for department in departments if department.name == "🥫 Бакалея")

    await db.set_product_department(normalize_product_name("молоко"), grocery.id)

    department = await resolve_department(db, "молоко")
    assert department.name == "🥫 Бакалея"
