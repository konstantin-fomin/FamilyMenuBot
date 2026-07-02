from aiogram import Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.types import Message

from app.database import Database, User
from app.handlers.common import ACCESS_DENIED_TEXT
from app.keyboards import main_menu_keyboard


router = Router(name="start")


@router.message(CommandStart())
async def start_command(message: Message, command: CommandObject, db: Database) -> None:
    if message.from_user is None:
        return

    telegram_id = message.from_user.id
    name = message.from_user.full_name
    existing_user = await db.get_user_by_telegram_id(telegram_id)
    if existing_user is not None:
        await message.answer(
            "Главное меню открыто.",
            reply_markup=main_menu_keyboard(),
        )
        return

    invite_code = _start_payload(message, command)
    if invite_code:
        invited_user = await db.consume_invitation(invite_code, telegram_id, name)
        if invited_user is not None:
            await message.answer(
                _member_welcome_text(),
                reply_markup=main_menu_keyboard(),
            )
            return

    owner = await db.create_owner_if_first(telegram_id, name)
    if owner is not None:
        await message.answer(
            _owner_welcome_text(),
            reply_markup=main_menu_keyboard(),
        )
        return

    await message.answer(ACCESS_DENIED_TEXT)


@router.message(Command("help"))
async def help_command(message: Message, db: Database) -> None:
    if message.from_user is None:
        return

    user = await db.get_user_by_telegram_id(message.from_user.id)
    if user is None:
        await message.answer(ACCESS_DENIED_TEXT)
        return

    await message.answer(_help_text(user), reply_markup=main_menu_keyboard())


def _owner_welcome_text() -> str:
    return (
        "Добро пожаловать в семейный бот меню 🍽️\n\n"
        "Я помогу хранить рецепты, составлять меню на неделю "
        "и собирать умный список покупок 🛒\n\n"
        "Вы стали владельцем семьи. Начните с добавления рецептов "
        "и пригласите близких через раздел «👨‍👩‍👧 Семья»."
    )


def _member_welcome_text() -> str:
    return (
        "Добро пожаловать в семейный бот меню 🍽️\n\n"
        "Теперь у вас есть доступ к общим рецептам, меню недели "
        "и списку покупок вашей семьи."
    )


def _start_payload(message: Message, command: CommandObject) -> str:
    if command.args:
        return command.args.strip()

    if not message.text:
        return ""

    parts = message.text.strip().split(maxsplit=1)
    if len(parts) != 2:
        return ""

    return parts[1].strip()


def _help_text(user: User) -> str:
    owner_hint = (
        "\n\nВы владелец семьи: пригласить близких можно в разделе «👨‍👩‍👧 Семья»."
        if user.role == "owner"
        else ""
    )
    return (
        "🍽 <b>Справка по семейному меню</b>\n\n"
        "📚 <b>Рецепты</b> — храните семейные блюда, ингредиенты и шаги приготовления.\n"
        "📅 <b>Меню недели</b> — собирайте блюда на текущую или следующую неделю.\n"
        "🛒 <b>Покупки</b> — создавайте список из меню, отмечайте купленное и добавляйте своё.\n"
        "👨‍👩‍👧 <b>Семья</b> — смотрите участников и приглашайте близких.\n\n"
        "Лучше начать с добавления нескольких рецептов, затем собрать меню недели "
        "и обновить список покупок."
        f"{owner_hint}"
    )
