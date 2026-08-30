# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.pact_service import end_pact as end_pact_service
from services.validation_service import require_faction


@app_commands.command(name="end", description="Dissolve a pact (leader only)")
@app_commands.describe(faction="Faction name (must be pact leader)", pact_id="Pact ID to dissolve")
@require_access_level(0)
async def end_pact(interaction: discord.Interaction, faction: str, pact_id: int):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)

    try:
        result = await end_pact_service(pact_id, faction_id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(
        title="Pact Dissolved",
        description=f"**{faction_data.display_name}** has dissolved the **{result['name']}** ({result['pact_type']}).\n\nAll members have been released."
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(end_pact)
