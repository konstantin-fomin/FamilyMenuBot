import pytest

from app.database import Database
from app.services.invitations import build_invite_link


@pytest.fixture
async def db(tmp_path):
    database = Database(tmp_path / "bot.db")
    await database.connect()
    await database.init_schema()
    try:
        yield database
    finally:
        await database.close()


@pytest.mark.asyncio
async def test_owner_can_create_one_time_invitation(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    invitation = await db.create_invitation(owner.id)

    member = await db.consume_invitation(
        invitation.code,
        telegram_id=2,
        name="Борис",
    )
    second_attempt = await db.consume_invitation(
        invitation.code,
        telegram_id=3,
        name="Вера",
    )

    assert member is not None
    assert member.role == "member"
    assert second_attempt is None
    assert await db.get_user_by_telegram_id(3) is None


@pytest.mark.asyncio
async def test_invalid_invitation_is_rejected(db):
    await db.create_owner_if_first(telegram_id=1, name="Анна")

    member = await db.consume_invitation(
        "wrong-code",
        telegram_id=2,
        name="Борис",
    )

    assert member is None
    assert await db.get_user_by_telegram_id(2) is None


def test_invitation_link_uses_required_bot_username():
    assert build_invite_link("abc123") == "https://t.me/Family_Menuu_Bot?start=abc123"
