# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from services.faction_service import search_faction_names
from services.map_service import search_world_names
from services.building_service import search_building_names


async def faction_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    names = await search_faction_names(current, 25)
    return [app_commands.Choice(name=name, value=name) for name in names]


async def world_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    names = await search_world_names(current, 25)
    return [app_commands.Choice(name=name, value=name) for name in names]


async def building_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    buildings = await search_building_names(current, 25)
    return [app_commands.Choice(name=f"{b.name} (ID: {b.id})", value=str(b.id)) for b in buildings]
