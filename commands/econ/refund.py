# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return, parse_currency
from utils.faction_utils import hex_to_int
from services.transfer_service import add_resources
from repositories.econ_repo import get_resource_ids_by_names
from services.validation_service import require_faction, require_world

LOCAL_RESOURCES = {'CM', 'EL', 'CS', 'U-CM', 'U-EL', 'U-CS', 'Population'}
GLOBAL_RESOURCES = {'ER', 'Influence'}


@app_commands.command(name="refund", description="Refund unregistered items")
@app_commands.describe(
    faction="Name of the faction receiving the refund",
    items="Description of items being refunded",
    amount="Amount in format: 1000 ER, 500 CM, etc. (comma separated)",
    world="World name (required for local resources: CM, EL, CS, Population, etc.)"
)
@require_access_level(0)
async def refund(
    interaction: discord.Interaction,
    faction: str,
    items: str,
    amount: str,
    world: Optional[str] = None
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)

    try:
        costs = parse_currency(amount)
    except Exception as e:
        await interaction.followup.send(embed=error_embed("Error", f"Invalid amount format: {e}"))
        return

    needs_world = any(c['resource'] in LOCAL_RESOURCES for c in costs)
    if needs_world and not world:
        await interaction.followup.send(
            embed=error_embed("Error", "World name is required for local resources (CM, EL, CS, Population, etc.).")
        )
        return

    world_id = None
    world_name = None
    if world:
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_id = r_world.data['id']
        world_name = r_world.data['name']

    resources_dict = {c['resource']: c['amount'] for c in costs}
    resource_names = list(resources_dict.keys())
    if len(await get_resource_ids_by_names(resource_names)) != len(resource_names):
        await interaction.followup.send(embed=error_embed("Error", "One or more invalid resource types."))
        return

    global_resources = {k: v for k, v in resources_dict.items() if k in GLOBAL_RESOURCES}
    local_resources = {k: v for k, v in resources_dict.items() if k not in GLOBAL_RESOURCES}

    try:
        if global_resources:
            await add_resources(faction_id, None, global_resources, is_refund=True)
        if local_resources:
            await add_resources(faction_id, world_id, local_resources, is_refund=True)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    cost_str = ", ".join([f"{handle_return(c['amount'])} {c['resource']}" for c in costs])
    loc_str = f" on **{world_name}**" if world_id and local_resources else ""
    embed = success_embed(
        title="Refund Complete",
        description=f"**{faction_data.display_name}** has been refunded {items} for {cost_str}{loc_str}"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(refund)
