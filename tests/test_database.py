import pytest

from app.database import Database


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
async def test_first_user_becomes_owner(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")

    assert owner is not None
    assert owner.telegram_id == 1
    assert owner.role == "owner"
    assert await db.users_count() == 1


@pytest.mark.asyncio
async def test_second_user_without_invite_does_not_become_owner(db):
    await db.create_owner_if_first(telegram_id=1, name="Анна")
    second = await db.create_owner_if_first(telegram_id=2, name="Борис")

    assert second is None
    assert await db.get_user_by_telegram_id(2) is None
    assert await db.users_count() == 1


@pytest.mark.asyncio
async def test_list_users_orders_owner_first(db):
    owner = await db.create_owner_if_first(telegram_id=1, name="Анна")
    invitation = await db.create_invitation(owner.id)
    await db.consume_invitation(invitation.code, telegram_id=2, name="Борис")

    users = await db.list_users()

    assert [user.role for user in users] == ["owner", "member"]
