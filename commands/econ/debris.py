# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import discord
from discord import app_commands
import random
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.fleet_service import list_debris_fleets, salvage_fleet
from services.transfer_service import add_resources
from services.validation_service import require_faction, require_world
from utils.autocomplete import faction_autocomplete, world_autocomplete, debris_autocomplete
from services.user_service import get_user_access_level
from services.intelligence_service import (
    get_user_faction_id,
    has_presence_at_world,
    get_observed_worlds,
)

REF_ACCESS_LEVEL = 4


class DebrisGroup(app_commands.Group):
    def __init__(self):
        super().__init__(name="debris", description="Manage debris")

debris_group = DebrisGroup()


@debris_group.command(name="list", description="List all debris fleets")
@app_commands.describe(
    faction="Filter by faction",
    world="Filter by world",
    ref="Referee mode: see every debris field in full. Never private."
)
@require_access_level(0)
async def debris_list(interaction: discord.Interaction, faction: Optional[str] = None, world: Optional[str] = None, ref: bool = False):
    await interaction.response.defer()

    if ref:
        viewer_level = await get_user_access_level(interaction.user.id)
        if viewer_level < REF_ACCESS_LEVEL:
            await interaction.followup.send(embed=error_embed("Error", "Referee mode requires elevated access."))
            return

    viewer_faction_id = None if ref else await get_user_faction_id(interaction.user.id)

    faction_id = None
    world_id = None

    if faction and world:
        r_faction_data, r_world = await asyncio.gather(require_faction(faction), require_world(world))
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        faction_id = r_faction_data.data.id
        world_id = r_world.data['id']
    elif faction:
        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        faction_id = r_faction_data.data.id
    elif world:
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_id = r_world.data['id']

    if not ref:
        if viewer_faction_id is None:
            await interaction.followup.send(embed=error_embed(
                "Intelligence insufficient",
                "You do not lead a faction. Use `ref:true` to view debris openly."
            ))
            return

        if world_id is not None and not await has_presence_at_world(viewer_faction_id, world_id):
            await interaction.followup.send(embed=error_embed(
                "Intelligence insufficient",
                "You have no units or territory at this world."
            ))
            return

    rows = await list_debris_fleets(faction_id=faction_id, world_id=world_id)

    if rows and not ref:
        observed = await get_observed_worlds(viewer_faction_id)
        rows = [r for r in rows if r['faction_id'] == viewer_faction_id or r['world_id'] in observed]

    if not rows:
        filter_text = (f" for {faction}" if faction else "") + (f" at {world}" if world else "")
        await interaction.followup.send(embed=error_embed("No Debris Found", f"No debris fleets found{filter_text}."))
        return

    LIMIT = 20
    lines = []
    for r in rows[:LIMIT]:
        fname = r['name'] or f"Fleet #{r['faction_fleet_number']}"
        lines.append(f"**{r['faction_name']}** — {fname} (ID: {r['faction_fleet_number']}) at **{r['world_name']}** • {r['total_cs']:,} CS")
    footer = f"Total: {len(rows)}" + (f" • Showing top {LIMIT}" if len(rows) > LIMIT else "")

    embed = discord.Embed(title="Debris", description="\n".join(lines), color=0x95a5a6)
    embed.set_footer(text=footer)
    await interaction.followup.send(embed=embed)


@debris_group.command(name="salvage", description="Salvage debris from destroyed fleets")
@app_commands.describe(
    faction="Name of the faction salvaging",
    debris="Debris fleet to salvage"
)
@require_access_level(0)
async def debris_salvage(
    interaction: discord.Interaction,
    faction: str,
    debris: str
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    try:
        debris_fleet_id = int(debris)
    except ValueError:
        return await interaction.followup.send(embed=error_embed("Error", f"Debris fleet '{debris}' not found."))

    faction_color = hex_to_int(faction_data.color)

    try:
        result = await salvage_fleet(faction_data.id, debris_fleet_id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    costs = result['costs']
    if not costs:
        await interaction.followup.send(embed=error_embed("Salvage Failed", "Debris had no salvageable materials."))
        return

    salvaged = {name: random.randint(0, int(worth) // 10) for name, worth in costs.items()}
    salvaged = {k: v for k, v in salvaged.items() if v > 0}

    if not salvaged:
        await interaction.followup.send(embed=error_embed("Salvage Failed", "Nothing of value could be recovered from the debris."))
        return

    await add_resources(faction_data.id, result['world_id'], salvaged)

    salvage_str = ", ".join([f"{handle_return(v)} {k}" for k, v in salvaged.items()])
    embed = success_embed(
        title="Salvage Complete",
        description=f"**{faction_data.display_name}** salvaged {salvage_str} from fleet #{debris_fleet_id}."
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(debris_group)
    list_cmd = debris_group.get_command('list')
    if list_cmd:
        list_cmd.autocomplete('faction')(faction_autocomplete)
        list_cmd.autocomplete('world')(world_autocomplete)
    salvage_cmd = debris_group.get_command('salvage')
    if salvage_cmd:
        salvage_cmd.autocomplete('faction')(faction_autocomplete)
        salvage_cmd.autocomplete('debris')(debris_autocomplete)
