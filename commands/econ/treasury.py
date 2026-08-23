# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import error_embed
from utils.embeds import send_response
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.fleet_service import get_total_faction_infantry
from database.static_cache import static_cache
from services.validation_service import require_faction, require_world
from repositories.econ_repo import (
    get_resource_treasury_scope,
    get_local_resource_by_world,
    get_global_resource_amount,
    get_local_treasury_for_world,
    get_global_treasury,
    get_local_treasury_aggregated,
)


@app_commands.command(name="treasury", description="View faction's resources")
@app_commands.describe(faction="Faction name", world="World name", resource="Resource name")
@require_access_level(0)
@ephemeral_capable('faction')
async def treasury(
    interaction: discord.Interaction,
    faction: str,
    world: Optional[str] = None,
    resource: Optional[str] = None
):
    await defer_response(interaction)

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)

    if resource:
        res_name = resource.upper()
        res_exists = static_cache.get_resource(resource)
        if not res_exists:
            await interaction.followup.send(embed=error_embed("Error", f"Resource `{resource}` not found."))
            return

        actual_name = res_exists['name']
        scope = await get_resource_treasury_scope(res_name)
        local_check = scope['is_local']
        global_check = scope['is_global']

        if local_check:
            rows = await get_local_resource_by_world(faction_id, res_exists['id'])
            embed = discord.Embed(title=f"Treasury ({actual_name}): {faction_data.display_name} per World", color=faction_color)
            total = 0
            lines = []
            for row in rows:
                if row['amount'] > 0:
                    lines.append(f"**{row['world_name']}**: {handle_return(row['amount'])}")
                    total += row['amount']
            embed.description = "\n".join(lines) if lines else f"No {actual_name} stored on any world."
            if lines:
                embed.set_footer(text=f"Total: {handle_return(total)}")
        elif global_check:
            amount = await get_global_resource_amount(faction_id, res_exists['id'])
            embed = discord.Embed(title=f"Treasury ({actual_name}): {faction_data.display_name}", color=faction_color)
            embed.description = f"{actual_name} is a global resource (not world-specific).\n**Total:** {handle_return(amount)}"
        else:
            await interaction.followup.send(embed=error_embed("Error", f"`{actual_name}` has no treasury data."))
            return

        await send_response(interaction, embed=embed)
        return

    if world:
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_data = r_world.data
        resources = await get_local_treasury_for_world(faction_id, world_data['id'])
        title = f"Treasury - {faction_data.display_name} on {world_data['name']}"
    else:
        (global_res, local_res), total_infantry = await asyncio.gather(
            asyncio.gather(
                get_global_treasury(faction_id),
                get_local_treasury_aggregated(faction_id)
            ),
            get_total_faction_infantry(faction_id)
        )
        resources = global_res + local_res
        if total_infantry > 0:
            resources = [r for r in resources if r['name'] != 'Military']
            resources.append({'name': 'Military', 'amount': total_infantry})
        title = f"Treasury - {faction_data.display_name} (Overall)"

    embed = discord.Embed(title=title, description="Current resource amounts", color=faction_color)
    for r in resources:
        if r['amount'] > 0:
            embed.add_field(name=r['name'], value=handle_return(r['amount']), inline=True)

    if not any(r['amount'] > 0 for r in resources):
        embed.description = "No resources"

    await send_response(interaction, embed=embed)


async def setup(bot):
    bot.tree.add_command(treasury)
