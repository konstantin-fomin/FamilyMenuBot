from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv
import os


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = BASE_DIR / "data" / "bot.db"
BOT_USERNAME = "Family_Menuu_Bot"


@dataclass(frozen=True)
class Config:
    bot_token: str
    database_path: Path
    bot_username: str = BOT_USERNAME


def load_config() -> Config:
    load_dotenv(BASE_DIR / ".env")
    token = os.getenv("BOT_TOKEN", "").strip()
    if not _looks_like_bot_token(token):
        raise RuntimeError("BOT_TOKEN не найден или имеет неверный формат в .env")

    return Config(bot_token=token, database_path=DEFAULT_DATABASE_PATH)


def _looks_like_bot_token(token: str) -> bool:
    left, sep, right = token.partition(":")
    return bool(sep and left.isdigit() and right)
