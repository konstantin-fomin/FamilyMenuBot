from aiogram import F, Router
from aiogram.types import Message

from app.database import Database
from app.handlers.common import require_user


router = Router(name="menu")


@router.message(F.text.in_({"📚 Рецепты", "📅 Меню недели", "🛒 Покупки"}))
async def development_stub(message: Message, db: Database) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    await message.answer("🔧 Раздел в разработке")
