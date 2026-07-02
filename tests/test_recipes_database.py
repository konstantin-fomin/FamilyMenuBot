import pytest

from app.database import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(tmp_path / "bot.db")
    await database.connect()
    await database.init_schema()
    try:
        yield database
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_categories_are_seeded(db):
    categories = await db.list_categories_with_counts()

    assert [category.name for category in categories] == [
        "🍲 Супы",
        "🍖 Основные блюда",
        "🥗 Салаты и закуски",
        "🍰 Выпечка и десерты",
        "🥤 Напитки",
        "📦 Прочее",
    ]
    assert [category.recipes_count for category in categories] == [0, 0, 0, 0, 0, 0]


@pytest.mark.asyncio
async def test_recipe_crud(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    category = (await db.list_categories_with_counts())[0]

    recipe = await db.create_recipe(
        name="Куриный суп",
        category_id=category.id,
        steps="Варить 40 минут.",
        created_by=owner.id,
        ingredients=[
            {"name": "курица", "amount": 500, "unit": "г"},
            {"name": "соль", "amount": None, "unit": "по вкусу"},
        ],
    )

    stored = await db.get_recipe(recipe.id)
    assert stored.name == "Куриный суп"
    assert stored.category_name == "🍲 Супы"
    assert [(item.name, item.amount, item.unit) for item in stored.ingredients] == [
        ("курица", 500, "г"),
        ("соль", None, "по вкусу"),
    ]

    await db.update_recipe_name(recipe.id, "Суп с курицей")
    await db.update_recipe_steps(recipe.id, "Варить до готовности.")
    await db.update_recipe_ingredients(
        recipe.id,
        [{"name": "картошка", "amount": 6, "unit": "шт"}],
    )

    updated = await db.get_recipe(recipe.id)
    assert updated.name == "Суп с курицей"
    assert updated.steps == "Варить до готовности."
    assert [(item.name, item.amount, item.unit) for item in updated.ingredients] == [
        ("картошка", 6, "шт")
    ]

    assert await db.recipes_count() == 1
    assert len(await db.list_recipes()) == 1

    await db.delete_recipe(recipe.id)

    assert await db.get_recipe(recipe.id) is None
    assert await db.recipes_count() == 0
