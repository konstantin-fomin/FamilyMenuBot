from datetime import datetime
import sqlite3
import tarfile
from zoneinfo import ZoneInfo

import pytest

from app.database import Database
from app.services.backups import (
    BACKUP_DB_ARCNAME,
    create_database_backup_archive,
    send_database_backup,
)


@pytest.fixture
async def db(tmp_path):
    database = Database(tmp_path / "bot.db")
    await database.connect()
    await database.init_schema()
    await database.create_owner_if_first(telegram_id=1, name="Анна")
    try:
        yield database
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_create_database_backup_archive_contains_database_copy(db, tmp_path):
    now = datetime(2026, 7, 3, 12, 30, tzinfo=ZoneInfo("Europe/Berlin"))

    backup = create_database_backup_archive(db.path, tmp_path, now=now)

    assert backup.filename == "familymenu-backup-2026-07-03.tar.gz"
    assert backup.path.exists()
    assert backup.database_size_bytes > 0
    assert "Дата: 2026-07-03" in backup.caption
    assert "Размер базы:" in backup.caption

    with tarfile.open(backup.path, "r:gz") as archive:
        assert archive.getnames() == [BACKUP_DB_ARCNAME]
        archive.extractall(tmp_path / "extracted")

    copied_db_path = tmp_path / "extracted" / BACKUP_DB_ARCNAME
    connection = sqlite3.connect(copied_db_path)
    try:
        users_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        categories_count = connection.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
    finally:
        connection.close()

    assert users_count == 1
    assert categories_count > 0


@pytest.mark.asyncio
async def test_send_database_backup_removes_temporary_archive(db):
    class FakeBot:
        def __init__(self):
            self.document_path = None
            self.chat_id = None

        async def send_document(self, chat_id, document, caption):
            self.chat_id = chat_id
            self.document_path = document.path
            assert document.filename.startswith("familymenu-backup-")
            assert caption.startswith("Бэкап базы Family Menu")
            assert self.document_path.exists()

    bot = FakeBot()

    backup = await send_database_backup(bot, db.path, -1004325432825)

    assert bot.chat_id == -1004325432825
    assert bot.document_path == backup.path
    assert not backup.path.exists()
