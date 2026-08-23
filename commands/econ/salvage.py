# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
import random
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.fleet_service import salvage_fleet
from services.transfer_service import add_resources
from services.validation_service import require_faction


@app_commands.command(name="salvage", description="Salvage debris from destroyed fleets")
@app_commands.describe(
    faction="Name of the faction salvaging",
    debris_fleet_id="ID of the destroyed fleet to salvage"
)
@require_access_level(0)
async def salvage(
    interaction: discord.Interaction,
    faction: str,
    debris_fleet_id: int
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

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
    bot.tree.add_command(salvage)
