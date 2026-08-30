# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.pact_service import (
    get_pact_type,
    get_pact_type_names,
    create_pact as create_pact_service,
    create_intelligence_sharing_pact,
    calculate_intelligence_sharing_cost,
    INTELLIGENCE_SHARING_PACT_TYPE,
)
from services.validation_service import require_faction, require_world
from utils.autocomplete import faction_autocomplete, pact_type_autocomplete


@app_commands.command(name="create", description="Create a diplomatic pact")
@app_commands.describe(
    faction="Faction name (will be pact leader)",
    pact_name="Name of the pact",
    pact_type="Type of pact",
    worlds="Intelligence Sharing only: worlds to share, comma separated",
    domestic="Intelligence Sharing only: share unit and building visibility on the shared worlds",
    foreign="Intelligence Sharing only: also receive alerts a pact partner receives"
)
@app_commands.autocomplete(faction=faction_autocomplete, pact_type=pact_type_autocomplete)
@require_access_level(0)
async def create_pact(
    interaction: discord.Interaction,
    faction: str,
    pact_name: str,
    pact_type: str,
    worlds: str = None,
    domestic: bool = False,
    foreign: bool = False,
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)

    pact_type_data = await get_pact_type(pact_type)
    if not pact_type_data:
        valid_types = ", ".join(await get_pact_type_names())
        await interaction.followup.send(embed=error_embed("Error", f"Invalid pact type. Valid types: {valid_types}"))
        return

    if pact_type_data.name == INTELLIGENCE_SHARING_PACT_TYPE:
        if not worlds:
            await interaction.followup.send(embed=error_embed("Error", "Provide at least one world to share with the worlds parameter."))
            return
        if not domestic and not foreign:
            await interaction.followup.send(embed=error_embed("Error", "Enable at least one mode: domestic, foreign, or both."))
            return

        world_names = [w.strip() for w in worlds.split(',') if w.strip()]
        r_worlds = await asyncio.gather(*(require_world(w) for w in world_names))
        world_ids = []
        world_display_names = []
        for r_world in r_worlds:
            if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
            world_ids.append(r_world.data['id'])
            world_display_names.append(r_world.data['name'])

        try:
            result = await create_intelligence_sharing_pact(
                pact_name, pact_type_data.id, faction_id, world_ids, domestic, foreign
            )
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Negative Influence Income", str(e)))
            return

        pact_id = result['pact_id']
        cost_per_member = calculate_intelligence_sharing_cost(len(world_ids), 1, domestic, foreign)
        modes = []
        if domestic:
            modes.append("Domestic (unit and building visibility)")
        if foreign:
            modes.append("Foreign (shared alerts)")

        embed = success_embed(
            title="Pact Created",
            description=f"**{faction_data.display_name}** has created the **{pact_name}** ({pact_type}).\n\n"
                        f"**Pact ID:** {pact_id}\n"
                        f"**Shared Worlds:** {', '.join(world_display_names)}\n"
                        f"**Modes:** {', '.join(modes)}\n"
                        f"**Current Cost:** {cost_per_member} Influence per member\n"
                        f"**Leader:** {faction_data.display_name}\n\n"
                        f"Other factions can join with `/pact join-intelligence-sharing {pact_id}`"
        )
        embed.color = faction_color
        await interaction.followup.send(embed=embed)
        return

    try:
        result = await create_pact_service(pact_name, pact_type_data.id, faction_id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Negative Influence Income", str(e)))
        return

    pact_id = result['pact_id']

    influence_cost = pact_type_data.influence_cost or 0
    embed = success_embed(
        title="Pact Created",
        description=f"**{faction_data.display_name}** has created the **{pact_name}** ({pact_type}).\n\n"
                    f"**Pact ID:** {pact_id}\n"
                    f"**Influence Cost:** {influence_cost} per additional member\n"
                    f"**Leader:** {faction_data.display_name}\n\n"
                    f"Other factions can join with `/join-pact {pact_id}`"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(create_pact)
