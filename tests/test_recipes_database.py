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
        "🥩 Мясо",
        "🍽️ Полноценные блюда",
        "🥗 Салаты и закуски",
        "🍰 Выпечка и десерты",
        "🥤 Напитки",
        "📦 Прочее",
    ]
    assert [category.recipes_count for category in categories] == [0, 0, 0, 0, 0, 0, 0]


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
    assert stored.servings == 4
    assert [(item.name, item.amount, item.unit) for item in stored.ingredients] == [
        ("курица", 500, "г"),
        ("соль", None, "по вкусу"),
    ]

    await db.update_recipe_name(recipe.id, "Суп с курицей")
    await db.update_recipe_steps(recipe.id, "Варить до готовности.")
    await db.update_recipe_servings(recipe.id, 6)
    await db.update_recipe_ingredients(
        recipe.id,
        [{"name": "картошка", "amount": 6, "unit": "шт"}],
    )

    updated = await db.get_recipe(recipe.id)
    assert updated.name == "Суп с курицей"
    assert updated.steps == "Варить до готовности."
    assert updated.servings == 6
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
    assert recipe.servings == 4
    assert [(item.name, item.amount, item.unit) for item in recipe.ingredients] == [
        ("картошка", 3, "шт")
    ]


@pytest.mark.asyncio
async def test_init_schema_replaces_old_main_dishes_category(tmp_path):
    db_path = tmp_path / "old-category.db"
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
                photo_file_id TEXT,
                servings INTEGER NOT NULL DEFAULT 4 CHECK (servings > 0),
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
            INSERT INTO categories (name) VALUES ('🍖 Основные блюда');
            INSERT INTO recipes (name, category_id, steps, created_by)
            VALUES ('Курица с рисом', 1, 'Запечь.', 1);
            """
        )
        connection.commit()
    finally:
        connection.close()

    database = Database(db_path)
    await database.connect()
    try:
        await database.init_schema()
        categories = await database.list_categories_with_counts()
        recipe = await database.get_recipe(1)
    finally:
        await database.close()

    assert "🍖 Основные блюда" not in [category.name for category in categories]
    assert "🥩 Мясо" in [category.name for category in categories]
    assert recipe.category_name == "🍽️ Полноценные блюда"


@pytest.mark.asyncio
async def test_init_schema_migrates_menu_item_servings_from_recipe_without_data_loss(tmp_path):
    db_path = tmp_path / "old-menu.db"
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
                photo_file_id TEXT,
                servings INTEGER NOT NULL DEFAULT 4 CHECK (servings > 0)
            );
            CREATE TABLE menus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE menu_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                menu_id INTEGER NOT NULL,
                recipe_id INTEGER,
                recipe_name TEXT NOT NULL,
                day INTEGER CHECK (day IS NULL OR day BETWEEN 1 AND 7),
                count INTEGER NOT NULL DEFAULT 1 CHECK (count > 0)
            );
            INSERT INTO users (telegram_id, name, role) VALUES (1, 'Анна', 'owner');
            INSERT INTO categories (name) VALUES ('🍲 Супы');
            INSERT INTO recipes (name, category_id, steps, created_by, servings)
            VALUES ('Суп на шестерых', 1, 'Варить.', 1, 6);
            INSERT INTO menus (week_start) VALUES ('2026-06-29');
            INSERT INTO menu_items (menu_id, recipe_id, recipe_name, day, count)
            VALUES (1, 1, 'Суп на шестерых', 1, 2);
            """
        )
        connection.commit()
    finally:
        connection.close()

    database = Database(db_path)
    await database.connect()
    try:
        await database.init_schema()
        items = await database.list_menu_items(1)
        columns = _table_columns(database._db, "menu_items")
    finally:
        await database.close()

    assert "servings" in columns
    assert len(items) == 1
    assert items[0].recipe_name == "Суп на шестерых"
    assert items[0].count == 2
    assert items[0].servings == 6


@pytest.mark.asyncio
async def test_real_database_copy_survives_recipe_and_menu_migrations(tmp_path):
    if not REAL_DATABASE_PATH.exists():
        pytest.skip("Локальная data/bot.db отсутствует")

    db_copy = tmp_path / "bot.db"
    shutil.copy2(REAL_DATABASE_PATH, db_copy)
    before_recipes, before_ingredients, before_menu_items = _database_counts(db_copy)

    database = Database(db_copy)
    await database.connect()
    try:
        await database.init_schema()
        after_recipes = await database.recipes_count()
        recipe_columns = _table_columns(database._db, "recipes")
        menu_item_columns = _table_columns(database._db, "menu_items")
        department_count = len(await database.list_shopping_departments())
    finally:
        await database.close()

    after_recipes_raw, after_ingredients, after_menu_items = _database_counts(db_copy)

    assert after_recipes == before_recipes
    assert after_recipes_raw == before_recipes
    assert after_ingredients == before_ingredients
    assert after_menu_items == before_menu_items
    assert "photo_file_id" in recipe_columns
    assert "servings" in recipe_columns
    assert "servings" in menu_item_columns
    assert department_count == 8


def _database_counts(db_path: Path) -> tuple[int, int, int]:
    connection = sqlite3.connect(db_path)
    try:
        recipes = connection.execute("SELECT COUNT(*) FROM recipes").fetchone()[0]
        ingredients = connection.execute("SELECT COUNT(*) FROM recipe_ingredients").fetchone()[0]
        menu_items = connection.execute("SELECT COUNT(*) FROM menu_items").fetchone()[0]
    finally:
        connection.close()
    return recipes, ingredients, menu_items


def _table_columns(connection: sqlite3.Connection, table: str) -> set[str]:
    return {
        row[1]
        for row in connection.execute(f"PRAGMA table_info({table})").fetchall()
    }
