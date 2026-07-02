from aiogram.types import Message

from app.database import Database, User
from app.keyboards import main_menu_keyboard
from app.texts import ACCESS_DENIED_TEXT


async def require_user(message: Message, db: Database) -> User | None:
    if message.from_user is None:
        return None

    user = await db.get_user_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer(ACCESS_DENIED_TEXT)
    return user


async def send_main_menu(message: Message, text: str) -> None:
    await message.answer(text, reply_markup=main_menu_keyboard())
