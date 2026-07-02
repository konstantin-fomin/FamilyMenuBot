from app.config import BOT_USERNAME


def build_invite_link(code: str, bot_username: str = BOT_USERNAME) -> str:
    return f"https://t.me/{bot_username}?start={code}"
