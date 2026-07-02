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
            """
        )
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
