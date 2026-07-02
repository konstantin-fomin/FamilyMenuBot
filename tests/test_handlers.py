from dataclasses import dataclass

import pytest
from aiogram import Dispatcher
from aiogram.filters import CommandObject

from app.database import Database
from app.handlers import setup_routers
from app.handlers.menu import development_stub
from app.handlers.start import start_command
from app.keyboards import main_menu_keyboard
from app.texts import (
    ACCESS_DENIED_TEXT,
    DEVELOPMENT_SECTION_BUTTONS,
    DEVELOPMENT_STUB_TEXT,
)


@dataclass
class FakeUser:
    id: int
    first_name: str

    @property
    def full_name(self) -> str:
        return self.first_name


class FakeMessage:
    def __init__(self, user_id: int, name: str, text: str) -> None:
        self.from_user = FakeUser(id=user_id, first_name=name)
        self.text = text
        self.answers: list[str] = []
        self.reply_markups = []

    async def answer(self, text: str, reply_markup=None) -> None:
        self.answers.append(text)
        self.reply_markups.append(reply_markup)


@pytest.fixture
async def db(tmp_path):
    database = Database(tmp_path / "bot.db")
    await database.connect()
    await database.init_schema()
    try:
        yield database
    finally:
        await database.close()


def test_all_routers_are_registered():
    dispatcher = Dispatcher()
    setup_routers(dispatcher)

    assert [router.name for router in dispatcher.sub_routers] == [
        "start",
        "family",
        "menu",
    ]


@pytest.mark.asyncio
async def test_development_buttons_answer_stub(db):
    await db.create_owner_if_first(telegram_id=1, name="Анна")
    keyboard_texts = [button.text for row in main_menu_keyboard().keyboard for button in row]

    for button_text in DEVELOPMENT_SECTION_BUTTONS:
        assert button_text in keyboard_texts

        message = FakeMessage(user_id=1, name="Анна", text=button_text)
        await development_stub(message, db)

        assert message.answers == [DEVELOPMENT_STUB_TEXT]


@pytest.mark.asyncio
async def test_start_deep_link_consumes_invitation_and_adds_member(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    invitation = await db.create_invitation(owner.id)
    message = FakeMessage(user_id=2, name="Борис", text=f"/start {invitation.code}")
    command = CommandObject(command="start", args=invitation.code)

    await start_command(message, command, db)

    member = await db.get_user_by_telegram_id(2)
    stored_invitation = await db.get_invitation(invitation.code)

    assert member is not None
    assert member.role == "member"
    assert stored_invitation.used_by_user_id == member.id
    assert any("Теперь у вас есть доступ" in text for text in message.answers)


@pytest.mark.asyncio
async def test_start_deep_link_uses_raw_text_payload_fallback(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    invitation = await db.create_invitation(owner.id)
    message = FakeMessage(user_id=2, name="Борис", text=f"/start {invitation.code}")
    command = CommandObject(command="start", args=None)

    await start_command(message, command, db)

    member = await db.get_user_by_telegram_id(2)

    assert member is not None
    assert member.role == "member"
    assert any("Теперь у вас есть доступ" in text for text in message.answers)


@pytest.mark.asyncio
async def test_invitation_code_cannot_be_used_twice(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    invitation = await db.create_invitation(owner.id)

    first_message = FakeMessage(user_id=2, name="Борис", text=f"/start {invitation.code}")
    await start_command(
        first_message,
        CommandObject(command="start", args=invitation.code),
        db,
    )

    second_message = FakeMessage(user_id=3, name="Вера", text=f"/start {invitation.code}")
    await start_command(
        second_message,
        CommandObject(command="start", args=invitation.code),
        db,
    )

    assert await db.get_user_by_telegram_id(2) is not None
    assert await db.get_user_by_telegram_id(3) is None
    assert second_message.answers == [ACCESS_DENIED_TEXT]
