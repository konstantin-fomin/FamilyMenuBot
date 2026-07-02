import pytest
from aiogram.exceptions import TelegramBadRequest

from app.services.telegram import safe_edit_text


class FakeTelegramMessage:
    def __init__(self, error_text: str | None = None) -> None:
        self.error_text = error_text
        self.edits = []
        self.answers = []

    async def edit_text(self, text: str, reply_markup=None):
        self.edits.append((text, reply_markup))
        if self.error_text:
            raise TelegramBadRequest(method=None, message=self.error_text)
        return "edited"

    async def answer(self, text: str, reply_markup=None):
        self.answers.append((text, reply_markup))
        return "answered"


@pytest.mark.asyncio
async def test_safe_edit_text_ignores_message_not_modified():
    message = FakeTelegramMessage("Bad Request: message is not modified")

    result = await safe_edit_text(message, "Текст")

    assert result is None
    assert message.answers == []


@pytest.mark.asyncio
async def test_safe_edit_text_sends_new_message_when_edit_target_missing():
    message = FakeTelegramMessage("Bad Request: message to edit not found")

    result = await safe_edit_text(message, "Новый текст", reply_markup="keyboard")

    assert result == "answered"
    assert message.answers == [("Новый текст", "keyboard")]
