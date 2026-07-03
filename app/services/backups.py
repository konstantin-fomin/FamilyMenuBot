from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, time, timedelta
import logging
from pathlib import Path
import sqlite3
import tarfile
import tempfile
from zoneinfo import ZoneInfo

from aiogram import Bot
from aiogram.types import FSInputFile


BACKUP_TIMEZONE = ZoneInfo("Europe/Berlin")
BACKUP_TIME = time(hour=3, minute=0)
BACKUP_ARCHIVE_PREFIX = "familymenu-backup"
BACKUP_DB_ARCNAME = "data/bot.db"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BackupArchive:
    path: Path
    filename: str
    caption: str
    database_size_bytes: int


def create_database_backup_archive(
    database_path: Path | str,
    output_dir: Path | str,
    now: datetime | None = None,
) -> BackupArchive:
    source_path = Path(database_path)
    if not source_path.exists():
        raise FileNotFoundError(f"База данных не найдена: {source_path}")

    created_at = _berlin_now(now)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    filename = f"{BACKUP_ARCHIVE_PREFIX}-{created_at:%Y-%m-%d}.tar.gz"
    archive_path = output_path / filename
    database_size = source_path.stat().st_size

    with tempfile.TemporaryDirectory(prefix="familymenu-sqlite-copy-") as copy_dir:
        copy_path = Path(copy_dir) / "bot.db"
        _backup_sqlite_database(source_path, copy_path)

        with tarfile.open(archive_path, "w:gz") as archive:
            archive.add(copy_path, arcname=BACKUP_DB_ARCNAME)

    return BackupArchive(
        path=archive_path,
        filename=filename,
        caption=_backup_caption(created_at, database_size),
        database_size_bytes=database_size,
    )


async def send_database_backup(
    bot: Bot,
    database_path: Path | str,
    backup_chat_id: int,
    now: datetime | None = None,
) -> BackupArchive:
    with tempfile.TemporaryDirectory(prefix="familymenu-backup-") as temp_dir:
        backup = create_database_backup_archive(database_path, temp_dir, now)
        document = FSInputFile(backup.path, filename=backup.filename)
        await bot.send_document(
            chat_id=backup_chat_id,
            document=document,
            caption=backup.caption,
        )
        return backup


def start_backup_scheduler(
    bot: Bot,
    database_path: Path | str,
    backup_chat_id: int,
) -> asyncio.Task:
    return asyncio.create_task(
        _scheduled_backup_loop(bot, Path(database_path), backup_chat_id),
        name="daily-database-backup",
    )


async def _scheduled_backup_loop(
    bot: Bot,
    database_path: Path,
    backup_chat_id: int,
) -> None:
    logger.info(
        "Планировщик бэкапов запущен: ежедневно в 03:00 Europe/Berlin, chat_id=%s",
        backup_chat_id,
    )
    try:
        while True:
            delay = seconds_until_next_backup()
            logger.info("Следующий бэкап базы через %.0f секунд", delay)
            await asyncio.sleep(delay)
            try:
                backup = await send_database_backup(bot, database_path, backup_chat_id)
            except Exception:
                logger.exception("Не удалось отправить запланированный бэкап базы")
            else:
                logger.info("Запланированный бэкап отправлен: %s", backup.filename)
    except asyncio.CancelledError:
        logger.info("Планировщик бэкапов остановлен")
        raise


def seconds_until_next_backup(now: datetime | None = None) -> float:
    current = _berlin_now(now)
    target = datetime.combine(
        current.date(),
        BACKUP_TIME,
        tzinfo=BACKUP_TIMEZONE,
    )
    if current >= target:
        target += timedelta(days=1)
    return (target - current).total_seconds()


def _backup_sqlite_database(source_path: Path, copy_path: Path) -> None:
    source = sqlite3.connect(f"file:{source_path}?mode=ro", uri=True)
    try:
        destination = sqlite3.connect(copy_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
    finally:
        source.close()


def _backup_caption(created_at: datetime, database_size: int) -> str:
    return (
        "Бэкап базы Family Menu\n"
        f"Дата: {created_at:%Y-%m-%d}\n"
        f"Время: {created_at:%H:%M:%S} Europe/Berlin\n"
        f"Размер базы: {_format_bytes(database_size)}"
    )


def _format_bytes(size: int) -> str:
    if size < 1024:
        return f"{size} Б"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} КБ"
    return f"{size / 1024 / 1024:.1f} МБ"


def _berlin_now(now: datetime | None) -> datetime:
    if now is None:
        return datetime.now(BACKUP_TIMEZONE)
    if now.tzinfo is None:
        return now.replace(tzinfo=BACKUP_TIMEZONE)
    return now.astimezone(BACKUP_TIMEZONE)
