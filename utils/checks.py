import discord
from discord import app_commands
from typing import Optional
from services.user_service import get_user_access_level


class InsufficientAccessLevel(app_commands.CheckFailure):
    def __init__(self, required: int, current: int):
        self.required = required
        self.current = current
        super().__init__(f"Access level {required} required, you have {current}")


class TOSNotAccepted(app_commands.CheckFailure):
    pass


def require_access_level(level: int = 0):
    async def predicate(interaction: discord.Interaction) -> bool:
        user_level = await get_user_access_level(interaction.user.id)
        if user_level == -2:
            raise TOSNotAccepted()
        if user_level < level:
            raise InsufficientAccessLevel(level, user_level)
        return True
    return app_commands.check(predicate)


async def check_access_level(user_id: int, required_level: int = 0) -> tuple[bool, Optional[str]]:
    user_level = await get_user_access_level(user_id)
    if user_level == -2:
        return (False, "You must accept the Terms of Service to use this bot.")
    if user_level == -1:
        return (False, "You declined the Terms of Service. You cannot use this bot.")
    if user_level < required_level:
        return (False, f"Access level {required_level} required. You have level {user_level}.")
    return (True, None)
