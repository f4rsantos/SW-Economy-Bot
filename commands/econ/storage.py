import asyncio
import math
import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.embeds import send_response
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.building_efficiency_service import calculate_effective_efficiency, get_faction_efficiency_map
from services.validation_service import require_faction, require_world
from services.econ_query_service import (
    get_storable_resource_by_name_upper,
    get_world_storage_for_resource,
    get_storage_rows_for_world,
    get_storage_rows_overall,
    get_max_population_capacity,
)


@app_commands.command(name="storage", description="View faction's storage capacity")
@app_commands.describe(faction="Faction name", world="World name", resource="Resource name")
@require_access_level(0)
async def storage(
    interaction: discord.Interaction,
    faction: str,
    world: Optional[str] = None,
    resource: Optional[str] = None
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data['id']
    faction_color = hex_to_int(faction_data['color'])

    if resource:
        res_row = await get_storable_resource_by_name_upper(resource.upper())
        if not res_row:
            await interaction.followup.send(embed=error_embed("Error", f"`{resource}` is not a storable resource."))
            return

        rows = await get_world_storage_for_resource(faction_id, res_row['id'])

        eff = await calculate_effective_efficiency(faction_id, building_type='storage', resource_name=res_row['name'])
        embed = discord.Embed(title=f"Storage ({res_row['name']}) — {faction_data['display_name']} per World", color=faction_color)
        total = 0
        lines = []
        for row in rows:
            if row['capacity'] > 0:
                effective = math.floor(row['capacity'] * eff)
                lines.append(f"**{row['world_name']}**: {handle_return(effective)}")
                total += effective
        embed.description = "\n".join(lines) if lines else f"No storage capacity for {res_row['name']} on any world."
        if lines:
            embed.set_footer(text=f"Total: {handle_return(total)} | Efficiency: {eff:.0%}")
        await send_response(interaction, embed=embed)
        return

    if world:
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_data = r_world.data
        storage_data, max_pop, eff_map = await asyncio.gather(
            get_storage_rows_for_world(faction_id, world_data['id']),
            get_max_population_capacity(faction_id, world_data['id']),
            get_faction_efficiency_map(faction_id)
        )
        title = f"Storage - {faction_data['display_name']} on {world_data['name']}"
    else:
        storage_data, max_pop, eff_map = await asyncio.gather(
            get_storage_rows_overall(faction_id),
            get_max_population_capacity(faction_id),
            get_faction_efficiency_map(faction_id)
        )
        title = f"Storage - {faction_data['display_name']} (Overall)"

    embed = success_embed(title=title, description="Maximum storage capacity *(after efficiency)*")
    embed.color = faction_color
    has_storage = False
    for s in storage_data:
        if s['capacity'] > 0:
            eff = eff_map('storage', s['name'])
            embed.add_field(name=s['name'], value=handle_return(math.floor(s['capacity'] * eff)), inline=True)
            has_storage = True

    if not has_storage:
        embed.description = "No storage buildings"

    if max_pop > 0:
        embed.add_field(name="Max Population", value=handle_return(max_pop), inline=True)

    await send_response(interaction, embed=embed)


async def setup(bot):
    bot.tree.add_command(storage)
