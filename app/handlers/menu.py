from aiogram import F, Router
from aiogram.types import Message

from app.database import Database
from app.handlers.common import require_user
from app.texts import DEVELOPMENT_SECTION_BUTTONS, DEVELOPMENT_STUB_TEXT


router = Router(name="menu")


@router.message(F.text.in_(DEVELOPMENT_SECTION_BUTTONS))
async def development_stub(message: Message, db: Database) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    await message.answer(DEVELOPMENT_STUB_TEXT)
