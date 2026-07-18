import discord
from discord import app_commands
from services.faction_service import search_faction_names
from services.map_service import search_world_names


async def faction_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    names = await search_faction_names(current, 25)
    return [app_commands.Choice(name=name, value=name) for name in names]


async def world_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    names = await search_world_names(current, 25)
    return [app_commands.Choice(name=name, value=name) for name in names]
