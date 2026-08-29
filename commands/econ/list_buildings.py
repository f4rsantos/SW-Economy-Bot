# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level, ephemeral_capable, defer_response
from services.user_service import get_user_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.building_service import resolve_building, list_faction_buildings
from services.validation_service import require_faction, require_world
from services.intelligence_service import (
    get_user_faction_id,
    has_presence_at_world,
    get_observed_worlds,
    get_foreign_shared_worlds,
    filter_visible_buildings,
)
from utils.autocomplete import faction_autocomplete, world_autocomplete, building_autocomplete


REF_ACCESS_LEVEL = 4


@app_commands.command(name="list-buildings", description="View your faction's buildings")
@app_commands.describe(
    faction="Faction name",
    world="Optional: specific world name",
    building="Optional: building name or ID to filter by",
    ref="Referee mode: see every building in full. Never private."
)
@require_access_level(0)
@ephemeral_capable('faction')
async def list_buildings(
    interaction: discord.Interaction,
    faction: str,
    world: Optional[str] = None,
    building: Optional[str] = None,
    ref: bool = False
):
    await defer_response(interaction)

    if ref:
        viewer_level = await get_user_access_level(interaction.user.id)
        if viewer_level < REF_ACCESS_LEVEL:
            await interaction.followup.send(embed=error_embed("Error", "Referee mode requires elevated access."))
            return
        interaction.extras['ephemeral'] = False

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data.color)

    viewer_faction_id = None if ref else await get_user_faction_id(interaction.user.id)
    is_own = ref or (viewer_faction_id is not None and viewer_faction_id == faction_data.id)

    world_id = None
    world_display = None
    if world:
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_id = r_world.data['id']
        world_display = r_world.data['name']

        if not is_own:
            if viewer_faction_id is None:
                await interaction.followup.send(embed=error_embed(
                    "Intelligence insufficient",
                    "You do not lead a faction. Use `ref:true` to view buildings openly."
                ))
                return
            if not await has_presence_at_world(viewer_faction_id, world_id):
                await interaction.followup.send(embed=error_embed(
                    "Intelligence insufficient",
                    "You have no units or territory at this world."
                ))
                return

    building_id = None
    building_display = None
    if building:
        try:
            building_data = await resolve_building(building)
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", str(e)))
            return
        if not building_data:
            await interaction.followup.send(embed=error_embed("Error", f"Building '{building}' not found."))
            return
        building_id = building_data.id
        building_display = building_data.name

    buildings = await list_faction_buildings(faction_data.id, world_id, building_id)

    hidden_count = 0
    if not is_own:
        observed_worlds = await get_observed_worlds(viewer_faction_id) if viewer_faction_id is not None else set()
        foreign_worlds = await get_foreign_shared_worlds(viewer_faction_id) if viewer_faction_id is not None else {}
        buildings, hidden_count = filter_visible_buildings(
            buildings, False, observed_worlds, foreign_worlds, faction_data.id
        )

    title_parts = [faction_data.display_name]
    if building_display:
        title_parts.append(building_display)
    if world_display:
        title_parts.append(f"on {world_display}")
    title = " - ".join(title_parts) if len(title_parts) > 1 else f"{faction_data.display_name} - All Buildings"

    if not buildings:
        if hidden_count:
            embed = discord.Embed(
                title=title,
                description="Owned buildings by world",
                color=faction_color
            )
            embed.add_field(
                name="Unknown",
                value=f"{hidden_count:,} not identified",
                inline=False
            )
            await interaction.followup.send(embed=embed)
            return
        parts = []
        if building_display:
            parts.append(building_display)
        if world_display:
            parts.append(f"on {world_display}")
        location = f" ({', '.join(parts)})" if parts else ""
        await interaction.followup.send(embed=error_embed("No Buildings", f"No buildings found{location}."))
        return

    by_world: dict = {}
    total_weighted = 0
    for b in buildings:
        by_world.setdefault(b['world_name'], []).append(b)
        total_weighted += b['amount'] * b['level']

    embed = discord.Embed(title=title, description="Owned buildings by world", color=faction_color)
    for world_name, world_buildings in by_world.items():
        lines = []
        for b in world_buildings:
            level_str = f" L{b['level']}" if b['level'] > 1 else ""
            lines.append(f"{b['amount']:,}x {b['name']}{level_str}")
        embed.add_field(name=world_name, value="\n".join(lines), inline=False)

    if hidden_count:
        embed.add_field(name="Unknown", value=f"{hidden_count:,} not identified", inline=False)

    embed.set_footer(text=f"Total weighted buildings: {total_weighted:,}")
    await interaction.followup.send(embed=embed)


async def setup(bot):
    list_buildings.autocomplete('faction')(faction_autocomplete)
    list_buildings.autocomplete('world')(world_autocomplete)
    list_buildings.autocomplete('building')(building_autocomplete)
    bot.tree.add_command(list_buildings)
