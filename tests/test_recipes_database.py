import sqlite3
from pathlib import Path
import shutil

import pytest

from app.database import Database


REAL_DATABASE_PATH = Path("data/bot.db")


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


@pytest.mark.asyncio
async def test_search_recipes_by_name_case_insensitive(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    category = (await db.list_categories_with_counts())[0]
    await db.create_recipe(
        name="Куриный суп",
        category_id=category.id,
        steps="",
        created_by=owner.id,
        ingredients=[{"name": "курица", "amount": 500, "unit": "г"}],
    )
    await db.create_recipe(
        name="Борщ",
        category_id=category.id,
        steps="",
        created_by=owner.id,
        ingredients=[{"name": "свёкла", "amount": 2, "unit": "шт"}],
    )

    recipes = await db.search_recipes("СУП")

    assert [recipe.name for recipe in recipes] == ["Куриный суп"]
    assert await db.search_recipes_count("суп") == 1
    assert await db.search_recipes_count("каша") == 0


@pytest.mark.asyncio
async def test_recipe_photo_can_be_stored_and_removed(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    category = (await db.list_categories_with_counts())[0]
    recipe = await db.create_recipe(
        name="Оладьи",
        category_id=category.id,
        steps="Жарить.",
        created_by=owner.id,
        ingredients=[{"name": "мука", "amount": 200, "unit": "г"}],
        photo_file_id="photo-1",
    )

    stored = await db.get_recipe(recipe.id)
    assert stored.photo_file_id == "photo-1"

    await db.update_recipe_photo(recipe.id, None)

    updated = await db.get_recipe(recipe.id)
    assert updated.photo_file_id is None


@pytest.mark.asyncio
async def test_init_schema_migrates_existing_recipes_without_data_loss(tmp_path):
    db_path = tmp_path / "old.db"
    connection = sqlite3.connect(db_path)
    try:
        connection.executescript(
            """
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL UNIQUE,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('owner', 'member')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );
            CREATE TABLE recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                steps TEXT NOT NULL DEFAULT '',
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (category_id) REFERENCES categories(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            );
            CREATE TABLE recipe_ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                amount REAL,
                unit TEXT NOT NULL,
                FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
            );
            INSERT INTO users (telegram_id, name, role) VALUES (1, 'Анна', 'owner');
            INSERT INTO categories (name) VALUES ('🍲 Супы');
            INSERT INTO recipes (name, category_id, steps, created_by)
            VALUES ('Старый суп', 1, 'Варить.', 1);
            INSERT INTO recipe_ingredients (recipe_id, name, amount, unit)
            VALUES (1, 'картошка', 3, 'шт');
            """
        )
        connection.commit()
    finally:
        connection.close()

    database = Database(db_path)
    await database.connect()
    try:
        await database.init_schema()
        recipe = await database.get_recipe(1)
    finally:
        await database.close()

    assert recipe.name == "Старый суп"
    assert recipe.steps == "Варить."
    assert recipe.photo_file_id is None
    assert [(item.name, item.amount, item.unit) for item in recipe.ingredients] == [
        ("картошка", 3, "шт")
    ]


@pytest.mark.asyncio
async def test_real_database_copy_survives_recipe_photo_migration(tmp_path):
    if not REAL_DATABASE_PATH.exists():
        pytest.skip("Локальная data/bot.db отсутствует")

    db_copy = tmp_path / "bot.db"
    shutil.copy2(REAL_DATABASE_PATH, db_copy)
    before_recipes, before_ingredients = _recipe_counts(db_copy)

    database = Database(db_copy)
    await database.connect()
    try:
        await database.init_schema()
        after_recipes = await database.recipes_count()
        columns = _table_columns(database._db, "recipes")
    finally:
        await database.close()

    after_recipes_raw, after_ingredients = _recipe_counts(db_copy)

    assert after_recipes == before_recipes
    assert after_recipes_raw == before_recipes
    assert after_ingredients == before_ingredients
    assert "photo_file_id" in columns


def _recipe_counts(db_path: Path) -> tuple[int, int]:
    connection = sqlite3.connect(db_path)
    try:
        recipes = connection.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
        ingredients = connection.execute("SELECT COUNT(*) FROM recipe_ingredients").fetchone()[0]
    finally:
        connection.close()
    return recipes, ingredients


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
