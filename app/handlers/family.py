from aiogram import F, Router
from aiogram.types import CallbackQuery, Message

from app.database import Database, User
from app.handlers.common import ACCESS_DENIED_TEXT, require_user
from app.keyboards import family_keyboard
from app.services.invitations import build_invite_link


router = Router(name="family")


@router.message(F.text == "👨‍👩‍👧 Семья")
async def family_section(message: Message, db: Database) -> None:
    user = await require_user(message, db)
    if user is None:
        return

    await message.answer(
        await _family_text(db),
        reply_markup=family_keyboard(user.role == "owner"),
    )


@router.callback_query(F.data == "family:invite")
async def invite_family_member(callback: CallbackQuery, db: Database) -> None:
    if callback.from_user is None:
        return

    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if user is None:
        await callback.answer(ACCESS_DENIED_TEXT, show_alert=True)
        return

    if user.role != "owner":
        await callback.answer("Приглашать может только владелец семьи.", show_alert=True)
        return

    invitation = await db.create_invitation(user.id)
    link = build_invite_link(invitation.code)
    await callback.message.answer(
        "Готово, вот одноразовая ссылка-приглашение:\n\n"
        f"{link}\n\n"
        "Отправьте её члену семьи. После первого входа ссылка станет недействительной."
    )
    await callback.answer()


async def _family_text(db: Database) -> str:
    users = await db.list_users()
    lines = ["👨‍👩‍👧 Семья", ""]
    lines.extend(_format_user(user) for user in users)
    return "\n".join(lines)


def _format_user(user: User) -> str:
    marker = "👑" if user.role == "owner" else "•"
    role = "владелец" if user.role == "owner" else "участник"
    return f"{marker} {user.name} — {role}"
