# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import discord
from discord import app_commands
from typing import Optional
from services.user_service import get_user_access_level, get_user_ephemeral


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


def ephemeral_capable(faction_param: str = "faction"):
    def predicate(interaction: discord.Interaction) -> bool:
        interaction.extras['ephemeral_param'] = faction_param
        return True
    return app_commands.check(predicate)


async def resolve_ephemeral(interaction: discord.Interaction) -> bool:
    param = interaction.extras.get('ephemeral_param')
    if not param:
        return False

    cached = interaction.extras.get('ephemeral')
    if cached is not None:
        return cached

    result = False
    try:
        if await get_user_ephemeral(interaction.user.id):
            faction_value = interaction.namespace.__dict__.get(param)
            if faction_value:
                from utils.faction_utils import leads_faction_named
                result = await leads_faction_named(interaction.user.id, faction_value)
    except Exception:
        result = False

    interaction.extras['ephemeral'] = result
    return result


async def defer_response(interaction: discord.Interaction, **kwargs):
    try:
        ephemeral = await asyncio.wait_for(resolve_ephemeral(interaction), timeout=1.0)
    except Exception:
        ephemeral = False
        interaction.extras['ephemeral'] = False
    await interaction.response.defer(ephemeral=ephemeral, **kwargs)
    return ephemeral


async def check_access_level(user_id: int, required_level: int = 0) -> tuple[bool, Optional[str]]:
    user_level = await get_user_access_level(user_id)
    if user_level == -2:
        return (False, "You must accept the Terms of Service to use this bot.")
    if user_level == -1:
        return (False, "You declined the Terms of Service. You cannot use this bot.")
    if user_level < required_level:
        return (False, f"Access level {required_level} required. You have level {user_level}.")
    return (True, None)
