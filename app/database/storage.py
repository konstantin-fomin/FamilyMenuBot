from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import secrets
import sqlite3
from typing import Literal


Role = Literal["owner", "member"]


@dataclass(frozen=True)
class User:
    id: int
    telegram_id: int
    name: str
    role: Role
    created_at: str


@dataclass(frozen=True)
class Invitation:
    id: int
    code: str
    created_by_user_id: int
    used_by_user_id: int | None
    created_at: str
    used_at: str | None


@dataclass(frozen=True)
class Category:
    id: int
    name: str
    recipes_count: int = 0


@dataclass(frozen=True)
class RecipeIngredient:
    id: int
    recipe_id: int
    name: str
    amount: float | None
    unit: str


@dataclass(frozen=True)
class Recipe:
    id: int
    name: str
    category_id: int
    category_name: str
    steps: str
    created_by: int
    created_at: str
    photo_file_id: str | None
    ingredients: list[RecipeIngredient]


@dataclass(frozen=True)
class RecipeSummary:
    id: int
    name: str
    category_id: int
    category_name: str
    created_at: str


@dataclass(frozen=True)
class Menu:
    id: int
    week_start: str
    created_at: str


@dataclass(frozen=True)
class MenuItem:
    id: int
    menu_id: int
    recipe_id: int | None
    recipe_name: str
    day: int | None
    count: int


@dataclass(frozen=True)
class ShoppingItem:
    id: int
    week_start: str
    name: str
    amount: float | None
    unit: str
    status: str
    source: str
    recipe_names: str
    position: int


DEFAULT_CATEGORIES = (
    "🍲 Супы",
    "🍖 Основные блюда",
    "🥗 Салаты и закуски",
    "🍰 Выпечка и десерты",
    "🥤 Напитки",
    "📦 Прочее",
)


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._connection: sqlite3.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path)
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        self._connection.commit()

    async def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    async def init_schema(self) -> None:
        db = self._db
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER NOT NULL UNIQUE,
                name TEXT NOT NULL,
                role TEXT NOT NULL CHECK (role IN ('owner', 'member')),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_users_telegram_id
                ON users (telegram_id);

            CREATE TABLE IF NOT EXISTS invitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT NOT NULL UNIQUE,
                created_by_user_id INTEGER NOT NULL,
                used_by_user_id INTEGER,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                used_at TEXT,
                FOREIGN KEY (created_by_user_id) REFERENCES users(id),
                FOREIGN KEY (used_by_user_id) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_invitations_code
                ON invitations (code);

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE
            );

            CREATE TABLE IF NOT EXISTS recipes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                category_id INTEGER NOT NULL,
                steps TEXT NOT NULL DEFAULT '',
                created_by INTEGER NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                photo_file_id TEXT,
                FOREIGN KEY (category_id) REFERENCES categories(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            );

            CREATE INDEX IF NOT EXISTS idx_recipes_category_id
                ON recipes (category_id);

            CREATE TABLE IF NOT EXISTS recipe_ingredients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipe_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                amount REAL,
                unit TEXT NOT NULL,
                FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_recipe_ingredients_recipe_id
                ON recipe_ingredients (recipe_id);

            CREATE TABLE IF NOT EXISTS menus (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS menu_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                menu_id INTEGER NOT NULL,
                recipe_id INTEGER,
                recipe_name TEXT NOT NULL,
                day INTEGER CHECK (day IS NULL OR day BETWEEN 1 AND 7),
                count INTEGER NOT NULL DEFAULT 1 CHECK (count > 0),
                FOREIGN KEY (menu_id) REFERENCES menus(id) ON DELETE CASCADE,
                FOREIGN KEY (recipe_id) REFERENCES recipes(id) ON DELETE SET NULL
            );

            CREATE INDEX IF NOT EXISTS idx_menu_items_menu_id
                ON menu_items (menu_id);

            CREATE UNIQUE INDEX IF NOT EXISTS idx_menu_items_unique_recipe_day
                ON menu_items (menu_id, recipe_id, day)
                WHERE recipe_id IS NOT NULL AND day IS NOT NULL;

            CREATE UNIQUE INDEX IF NOT EXISTS idx_menu_items_unique_recipe_no_day
                ON menu_items (menu_id, recipe_id)
                WHERE recipe_id IS NOT NULL AND day IS NULL;

            CREATE TABLE IF NOT EXISTS shopping_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                week_start TEXT NOT NULL,
                name TEXT NOT NULL,
                amount REAL,
                unit TEXT NOT NULL,
                status TEXT NOT NULL CHECK (status IN ('to_buy', 'have', 'bought')),
                source TEXT NOT NULL CHECK (source IN ('menu', 'manual')),
                recipe_names TEXT NOT NULL DEFAULT '',
                position INTEGER NOT NULL DEFAULT 0
            );

            CREATE INDEX IF NOT EXISTS idx_shopping_items_week_start
                ON shopping_items (week_start);
            """
        )
        self._ensure_recipe_photo_column()
        self._seed_categories()
        db.commit()

    async def get_user_by_telegram_id(self, telegram_id: int) -> User | None:
        row = self._fetchone(
            "SELECT id, telegram_id, name, role, created_at FROM users WHERE telegram_id = ?",
            (telegram_id,),
        )
        return _user_from_row(row) if row else None

    async def users_count(self) -> int:
        row = self._fetchone("SELECT COUNT(*) AS count FROM users")
        return int(row["count"])

    async def create_owner_if_first(self, telegram_id: int, name: str) -> User | None:
        db = self._db
        db.execute("BEGIN IMMEDIATE")
        try:
            row = self._fetchone("SELECT COUNT(*) AS count FROM users")
            if int(row["count"]) > 0:
                db.rollback()
                return None

            db.execute(
                "INSERT INTO users (telegram_id, name, role) VALUES (?, ?, 'owner')",
                (telegram_id, name),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

        user = await self.get_user_by_telegram_id(telegram_id)
        if user is None:
            raise RuntimeError("Не удалось создать владельца")
        return user

    async def create_member(self, telegram_id: int, name: str) -> User:
        self._db.execute(
            "INSERT INTO users (telegram_id, name, role) VALUES (?, ?, 'member')",
            (telegram_id, name),
        )
        self._db.commit()
        user = await self.get_user_by_telegram_id(telegram_id)
        if user is None:
            raise RuntimeError("Не удалось создать участника семьи")
        return user

    async def list_users(self) -> list[User]:
        cursor = self._db.execute(
            """
            SELECT id, telegram_id, name, role, created_at
            FROM users
            ORDER BY
                CASE role WHEN 'owner' THEN 0 ELSE 1 END,
                created_at,
                id
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        return [_user_from_row(row) for row in rows]

    async def create_invitation(self, owner_user_id: int) -> Invitation:
        code = secrets.token_urlsafe(8)
        self._db.execute(
            "INSERT INTO invitations (code, created_by_user_id) VALUES (?, ?)",
            (code, owner_user_id),
        )
        self._db.commit()
        invitation = await self.get_invitation(code)
        if invitation is None:
            raise RuntimeError("Не удалось создать приглашение")
        return invitation

    async def get_invitation(self, code: str) -> Invitation | None:
        row = self._fetchone(
            """
            SELECT id, code, created_by_user_id, used_by_user_id, created_at, used_at
            FROM invitations
            WHERE code = ?
            """,
            (code,),
        )
        return _invitation_from_row(row) if row else None

    async def consume_invitation(self, code: str, telegram_id: int, name: str) -> User | None:
        db = self._db
        db.execute("BEGIN IMMEDIATE")
        try:
            existing_user = self._fetchone(
                "SELECT id, telegram_id, name, role, created_at FROM users WHERE telegram_id = ?",
                (telegram_id,),
            )
            if existing_user is not None:
                db.rollback()
                return _user_from_row(existing_user)

            invitation = self._fetchone(
                """
                SELECT id
                FROM invitations
                WHERE code = ? AND used_by_user_id IS NULL
                """,
                (code,),
            )
            if invitation is None:
                db.rollback()
                return None

            cursor = db.execute(
                "INSERT INTO users (telegram_id, name, role) VALUES (?, ?, 'member')",
                (telegram_id, name),
            )
            new_user_id = cursor.lastrowid
            cursor.close()
            db.execute(
                """
                UPDATE invitations
                SET used_by_user_id = ?, used_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (new_user_id, invitation["id"]),
            )
            db.commit()
        except Exception:
            db.rollback()
            raise

        return await self.get_user_by_telegram_id(telegram_id)

    async def list_categories_with_counts(self) -> list[Category]:
        cursor = self._db.execute(
            """
            SELECT c.id, c.name, COUNT(r.id) AS recipes_count
            FROM categories c
            LEFT JOIN recipes r ON r.category_id = c.id
            GROUP BY c.id, c.name
            ORDER BY c.id
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        return [_category_from_row(row) for row in rows]

    async def get_category(self, category_id: int) -> Category | None:
        row = self._fetchone(
            """
            SELECT c.id, c.name, COUNT(r.id) AS recipes_count
            FROM categories c
            LEFT JOIN recipes r ON r.category_id = c.id
            WHERE c.id = ?
            GROUP BY c.id, c.name
            """,
            (category_id,),
        )
        return _category_from_row(row) if row else None

    async def create_recipe(
        self,
        name: str,
        category_id: int,
        steps: str,
        created_by: int,
        ingredients: list[dict],
        photo_file_id: str | None = None,
    ) -> Recipe:
        db = self._db
        db.execute("BEGIN IMMEDIATE")
        try:
            cursor = db.execute(
                """
                INSERT INTO recipes (name, category_id, steps, created_by, photo_file_id)
                VALUES (?, ?, ?, ?, ?)
                """,
                (name, category_id, steps, created_by, photo_file_id),
            )
            recipe_id = cursor.lastrowid
            cursor.close()
            self._replace_recipe_ingredients(recipe_id, ingredients)
            db.commit()
        except Exception:
            db.rollback()
            raise

        recipe = await self.get_recipe(recipe_id)
        if recipe is None:
            raise RuntimeError("Не удалось создать рецепт")
        return recipe

    async def get_recipe(self, recipe_id: int) -> Recipe | None:
        row = self._fetchone(
            """
            SELECT r.id, r.name, r.category_id, c.name AS category_name,
                   r.steps, r.created_by, r.created_at, r.photo_file_id
            FROM recipes r
            JOIN categories c ON c.id = r.category_id
            WHERE r.id = ?
            """,
            (recipe_id,),
        )
        if row is None:
            return None
        ingredients = await self.list_recipe_ingredients(recipe_id)
        return _recipe_from_row(row, ingredients)

    async def list_recipe_ingredients(self, recipe_id: int) -> list[RecipeIngredient]:
        cursor = self._db.execute(
            """
            SELECT id, recipe_id, name, amount, unit
            FROM recipe_ingredients
            WHERE recipe_id = ?
            ORDER BY id
            """,
            (recipe_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
        return [_ingredient_from_row(row) for row in rows]

    async def list_recipes(
        self,
        category_id: int | None = None,
        limit: int = 8,
        offset: int = 0,
    ) -> list[RecipeSummary]:
        params: list[int] = []
        where = ""
        if category_id is not None:
            where = "WHERE r.category_id = ?"
            params.append(category_id)
        params.extend([limit, offset])
        cursor = self._db.execute(
            f"""
            SELECT r.id, r.name, r.category_id, c.name AS category_name, r.created_at
            FROM recipes r
            JOIN categories c ON c.id = r.category_id
            {where}
            ORDER BY r.created_at DESC, r.id DESC
            LIMIT ? OFFSET ?
            """,
            tuple(params),
        )
        rows = cursor.fetchall()
        cursor.close()
        return [_recipe_summary_from_row(row) for row in rows]

    async def recipes_count(self, category_id: int | None = None) -> int:
        if category_id is None:
            row = self._fetchone("SELECT COUNT(*) AS count FROM recipes")
        else:
            row = self._fetchone(
                "SELECT COUNT(*) AS count FROM recipes WHERE category_id = ?",
                (category_id,),
            )
        return int(row["count"])

    async def search_recipes(
        self,
        query: str,
        limit: int = 8,
        offset: int = 0,
    ) -> list[RecipeSummary]:
        matches = await self._search_recipe_rows(query)
        return [_recipe_summary_from_row(row) for row in matches[offset : offset + limit]]

    async def search_recipes_count(self, query: str) -> int:
        return len(await self._search_recipe_rows(query))

    async def update_recipe_name(self, recipe_id: int, name: str) -> None:
        self._db.execute("UPDATE recipes SET name = ? WHERE id = ?", (name, recipe_id))
        self._db.commit()

    async def update_recipe_category(self, recipe_id: int, category_id: int) -> None:
        self._db.execute(
            "UPDATE recipes SET category_id = ? WHERE id = ?",
            (category_id, recipe_id),
        )
        self._db.commit()

    async def update_recipe_steps(self, recipe_id: int, steps: str) -> None:
        self._db.execute("UPDATE recipes SET steps = ? WHERE id = ?", (steps, recipe_id))
        self._db.commit()

    async def update_recipe_photo(self, recipe_id: int, photo_file_id: str | None) -> None:
        self._db.execute(
            "UPDATE recipes SET photo_file_id = ? WHERE id = ?",
            (photo_file_id, recipe_id),
        )
        self._db.commit()

    async def update_recipe_ingredients(self, recipe_id: int, ingredients: list[dict]) -> None:
        db = self._db
        db.execute("BEGIN IMMEDIATE")
        try:
            self._replace_recipe_ingredients(recipe_id, ingredients)
            db.commit()
        except Exception:
            db.rollback()
            raise

    async def delete_recipe(self, recipe_id: int) -> None:
        self._db.execute("DELETE FROM recipes WHERE id = ?", (recipe_id,))
        self._db.commit()

    async def get_or_create_menu(self, week_start: str) -> Menu:
        self._db.execute(
            "INSERT OR IGNORE INTO menus (week_start) VALUES (?)",
            (week_start,),
        )
        self._db.commit()
        menu = await self.get_menu_by_week_start(week_start)
        if menu is None:
            raise RuntimeError("Не удалось создать меню недели")
        return menu

    async def get_menu_by_week_start(self, week_start: str) -> Menu | None:
        row = self._fetchone(
            "SELECT id, week_start, created_at FROM menus WHERE week_start = ?",
            (week_start,),
        )
        return _menu_from_row(row) if row else None

    async def add_menu_item(
        self,
        menu_id: int,
        recipe_id: int,
        day: int | None,
        count: int = 1,
    ) -> MenuItem:
        recipe = await self.get_recipe(recipe_id)
        if recipe is None:
            raise ValueError("Рецепт не найден")

        existing = await self.find_menu_item(menu_id, recipe_id, day)
        if existing is not None:
            await self.change_menu_item_count(existing.id, existing.count + count)
            updated = await self.get_menu_item(existing.id)
            if updated is None:
                raise RuntimeError("Не удалось обновить блюдо в меню")
            return updated

        cursor = self._db.execute(
            """
            INSERT INTO menu_items (menu_id, recipe_id, recipe_name, day, count)
            VALUES (?, ?, ?, ?, ?)
            """,
            (menu_id, recipe_id, recipe.name, day, count),
        )
        item_id = cursor.lastrowid
        cursor.close()
        self._db.commit()
        item = await self.get_menu_item(item_id)
        if item is None:
            raise RuntimeError("Не удалось добавить блюдо в меню")
        return item

    async def find_menu_item(
        self,
        menu_id: int,
        recipe_id: int,
        day: int | None,
    ) -> MenuItem | None:
        if day is None:
            row = self._fetchone(
                """
                SELECT id, menu_id, recipe_id, recipe_name, day, count
                FROM menu_items
                WHERE menu_id = ? AND recipe_id = ? AND day IS NULL
                """,
                (menu_id, recipe_id),
            )
        else:
            row = self._fetchone(
                """
                SELECT id, menu_id, recipe_id, recipe_name, day, count
                FROM menu_items
                WHERE menu_id = ? AND recipe_id = ? AND day = ?
                """,
                (menu_id, recipe_id, day),
            )
        return _menu_item_from_row(row) if row else None

    async def get_menu_item(self, item_id: int) -> MenuItem | None:
        row = self._fetchone(
            """
            SELECT id, menu_id, recipe_id, recipe_name, day, count
            FROM menu_items
            WHERE id = ?
            """,
            (item_id,),
        )
        return _menu_item_from_row(row) if row else None

    async def list_menu_items(self, menu_id: int) -> list[MenuItem]:
        cursor = self._db.execute(
            """
            SELECT id, menu_id, recipe_id, recipe_name, day, count
            FROM menu_items
            WHERE menu_id = ?
            ORDER BY day IS NULL, day, id
            """,
            (menu_id,),
        )
        rows = cursor.fetchall()
        cursor.close()
        return [_menu_item_from_row(row) for row in rows]

    async def move_menu_item(self, item_id: int, day: int | None) -> MenuItem | None:
        item = await self.get_menu_item(item_id)
        if item is None:
            return None

        if item.recipe_id is not None:
            existing = await self.find_menu_item(item.menu_id, item.recipe_id, day)
            if existing is not None and existing.id != item.id:
                await self.change_menu_item_count(existing.id, existing.count + item.count)
                await self.delete_menu_item(item.id)
                return await self.get_menu_item(existing.id)

        self._db.execute("UPDATE menu_items SET day = ? WHERE id = ?", (day, item_id))
        self._db.commit()
        return await self.get_menu_item(item_id)

    async def change_menu_item_count(self, item_id: int, count: int) -> None:
        if count <= 0:
            await self.delete_menu_item(item_id)
            return
        self._db.execute("UPDATE menu_items SET count = ? WHERE id = ?", (count, item_id))
        self._db.commit()

    async def decrement_menu_item(self, item_id: int) -> None:
        item = await self.get_menu_item(item_id)
        if item is None:
            return
        await self.change_menu_item_count(item.id, item.count - 1)

    async def delete_menu_item(self, item_id: int) -> None:
        self._db.execute("DELETE FROM menu_items WHERE id = ?", (item_id,))
        self._db.commit()

    async def list_shopping_items(self, week_start: str) -> list[ShoppingItem]:
        cursor = self._db.execute(
            """
            SELECT id, week_start, name, amount, unit, status, source, recipe_names, position
            FROM shopping_items
            WHERE week_start = ?
            ORDER BY
                CASE status WHEN 'to_buy' THEN 0 WHEN 'have' THEN 1 ELSE 2 END,
                position,
                id
            """,
            (week_start,),
        )
        rows = cursor.fetchall()
        cursor.close()
        return [_shopping_item_from_row(row) for row in rows]

    async def shopping_items_count(self, week_start: str) -> int:
        row = self._fetchone(
            "SELECT COUNT(*) AS count FROM shopping_items WHERE week_start = ?",
            (week_start,),
        )
        return int(row["count"])

    async def get_shopping_item(self, item_id: int) -> ShoppingItem | None:
        row = self._fetchone(
            """
            SELECT id, week_start, name, amount, unit, status, source, recipe_names, position
            FROM shopping_items
            WHERE id = ?
            """,
            (item_id,),
        )
        return _shopping_item_from_row(row) if row else None

    async def create_shopping_item(
        self,
        week_start: str,
        name: str,
        amount: float | None,
        unit: str,
        status: str = "to_buy",
        source: str = "manual",
        recipe_names: str = "",
        position: int | None = None,
    ) -> ShoppingItem:
        if position is None:
            position = await self.next_shopping_position(week_start)
        cursor = self._db.execute(
            """
            INSERT INTO shopping_items
                (week_start, name, amount, unit, status, source, recipe_names, position)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (week_start, name, amount, unit, status, source, recipe_names, position),
        )
        item_id = cursor.lastrowid
        cursor.close()
        self._db.commit()
        item = await self.get_shopping_item(item_id)
        if item is None:
            raise RuntimeError("Не удалось создать позицию покупок")
        return item

    async def update_shopping_item_status(self, item_id: int, status: str) -> None:
        self._db.execute(
            "UPDATE shopping_items SET status = ? WHERE id = ?",
            (status, item_id),
        )
        self._db.commit()

    async def update_shopping_menu_item(
        self,
        item_id: int,
        name: str,
        amount: float | None,
        unit: str,
        recipe_names: str,
    ) -> None:
        self._db.execute(
            """
            UPDATE shopping_items
            SET name = ?, amount = ?, unit = ?, recipe_names = ?
            WHERE id = ?
            """,
            (name, amount, unit, recipe_names, item_id),
        )
        self._db.commit()

    async def delete_shopping_item(self, item_id: int) -> None:
        self._db.execute("DELETE FROM shopping_items WHERE id = ?", (item_id,))
        self._db.commit()

    async def delete_bought_shopping_items(self, week_start: str) -> int:
        cursor = self._db.execute(
            "DELETE FROM shopping_items WHERE week_start = ? AND status = 'bought'",
            (week_start,),
        )
        deleted = cursor.rowcount
        cursor.close()
        self._db.commit()
        return deleted

    async def delete_missing_menu_shopping_items(self, week_start: str, keep_ids: list[int]) -> None:
        if keep_ids:
            placeholders = ",".join("?" for _ in keep_ids)
            self._db.execute(
                f"""
                DELETE FROM shopping_items
                WHERE week_start = ? AND source = 'menu' AND id NOT IN ({placeholders})
                """,
                (week_start, *keep_ids),
            )
        else:
            self._db.execute(
                "DELETE FROM shopping_items WHERE week_start = ? AND source = 'menu'",
                (week_start,),
            )
        self._db.commit()

    async def next_shopping_position(self, week_start: str) -> int:
        row = self._fetchone(
            "SELECT COALESCE(MAX(position), 0) + 1 AS position FROM shopping_items WHERE week_start = ?",
            (week_start,),
        )
        return int(row["position"])

    def _replace_recipe_ingredients(self, recipe_id: int, ingredients: list[dict]) -> None:
        self._db.execute("DELETE FROM recipe_ingredients WHERE recipe_id = ?", (recipe_id,))
        self._db.executemany(
            """
            INSERT INTO recipe_ingredients (recipe_id, name, amount, unit)
            VALUES (?, ?, ?, ?)
            """,
            [
                (
                    recipe_id,
                    ingredient["name"],
                    ingredient.get("amount"),
                    ingredient["unit"],
                )
                for ingredient in ingredients
            ],
        )

    def _ensure_recipe_photo_column(self) -> None:
        columns = {
            row["name"]
            for row in self._db.execute("PRAGMA table_info(recipes)").fetchall()
        }
        if "photo_file_id" not in columns:
            self._db.execute("ALTER TABLE recipes ADD COLUMN photo_file_id TEXT")

    async def _search_recipe_rows(self, query: str) -> list[sqlite3.Row]:
        normalized_query = query.strip().casefold()
        if not normalized_query:
            return []

        cursor = self._db.execute(
            """
            SELECT r.id, r.name, r.category_id, c.name AS category_name, r.created_at
            FROM recipes r
            JOIN categories c ON c.id = r.category_id
            ORDER BY r.created_at DESC, r.id DESC
            """
        )
        rows = cursor.fetchall()
        cursor.close()
        return [
            row
            for row in rows
            if normalized_query in str(row["name"]).casefold()
        ]

    def _seed_categories(self) -> None:
        self._db.executemany(
            "INSERT OR IGNORE INTO categories (name) VALUES (?)",
            [(name,) for name in DEFAULT_CATEGORIES],
        )

    def _fetchone(self, query: str, params: tuple = ()) -> sqlite3.Row | None:
        cursor = self._db.execute(query, params)
        row = cursor.fetchone()
        cursor.close()
        return row

    @property
    def _db(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("Database.connect() must be called first")
        return self._connection


def _user_from_row(row: sqlite3.Row) -> User:
    return User(
        id=row["id"],
        telegram_id=row["telegram_id"],
        name=row["name"],
        role=row["role"],
        created_at=row["created_at"],
    )


def _invitation_from_row(row: sqlite3.Row) -> Invitation:
    return Invitation(
        id=row["id"],
        code=row["code"],
        created_by_user_id=row["created_by_user_id"],
        used_by_user_id=row["used_by_user_id"],
        created_at=row["created_at"],
        used_at=row["used_at"],
    )


def _category_from_row(row: sqlite3.Row) -> Category:
    return Category(
        id=row["id"],
        name=row["name"],
        recipes_count=row["recipes_count"],
    )


def _ingredient_from_row(row: sqlite3.Row) -> RecipeIngredient:
    return RecipeIngredient(
        id=row["id"],
        recipe_id=row["recipe_id"],
        name=row["name"],
        amount=row["amount"],
        unit=row["unit"],
    )


def _recipe_from_row(row: sqlite3.Row, ingredients: list[RecipeIngredient]) -> Recipe:
    return Recipe(
        id=row["id"],
        name=row["name"],
        category_id=row["category_id"],
        category_name=row["category_name"],
        steps=row["steps"],
        created_by=row["created_by"],
        created_at=row["created_at"],
        photo_file_id=row["photo_file_id"],
        ingredients=ingredients,
    )


def _recipe_summary_from_row(row: sqlite3.Row) -> RecipeSummary:
    return RecipeSummary(
        id=row["id"],
        name=row["name"],
        category_id=row["category_id"],
        category_name=row["category_name"],
        created_at=row["created_at"],
    )


def _menu_from_row(row: sqlite3.Row) -> Menu:
    return Menu(
        id=row["id"],
        week_start=row["week_start"],
        created_at=row["created_at"],
    )


def _menu_item_from_row(row: sqlite3.Row) -> MenuItem:
    return MenuItem(
        id=row["id"],
        menu_id=row["menu_id"],
        recipe_id=row["recipe_id"],
        recipe_name=row["recipe_name"],
        day=row["day"],
        count=row["count"],
    )


def _shopping_item_from_row(row: sqlite3.Row) -> ShoppingItem:
    return ShoppingItem(
        id=row["id"],
        week_start=row["week_start"],
        name=row["name"],
        amount=row["amount"],
        unit=row["unit"],
        status=row["status"],
        source=row["source"],
        recipe_names=row["recipe_names"],
        position=row["position"],
    )
