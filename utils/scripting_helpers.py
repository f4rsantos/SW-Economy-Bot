from __future__ import annotations
import discord
from utils.faction_utils import get_faction_by_name
from services.user_service import get_user_access_level

ADMIN_LEVEL = 9


async def resolve_faction_with_access(
    interaction: discord.Interaction,
    faction_name: str,
) -> tuple:
    faction = await get_faction_by_name(faction_name)
    if not faction:
        return None, f"Faction '{faction_name}' not found."

    user_level = await get_user_access_level(interaction.user.id)
    is_leader = faction["leader_id"] == interaction.user.id
    is_admin = user_level >= ADMIN_LEVEL

    if not is_leader and not is_admin:
        return None, "You must be the faction's leader or an administrator to manage scripts."

    return dict(faction), None


def trigger_day_from_ast(ast) -> str | None:
    if ast.directives:
        day = ast.directives[0].day
        if day == "TRIGGER":
            return None
        return day
    return None


def trigger_type_from_ast(ast) -> str | None:
    if ast.directives:
        day = ast.directives[0].day
        if day == "TRIGGER":
            return "manual"
        return "scheduled"
    return None
