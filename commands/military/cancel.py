# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.recruit_service import cancel_recruitment
from services.validation_service import require_faction


@app_commands.command(name="cancel", description="Cancel a pending military recruitment")
@app_commands.describe(
    faction="Faction name",
    recruitment_id="ID of the recruitment to cancel (from /military progress)"
)
@require_access_level(0)
@ephemeral_capable('faction')
async def cancel(interaction: discord.Interaction, faction: str, recruitment_id: int):
    await defer_response(interaction)

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)
    display_name = faction_data.display_name

    cancelled = await cancel_recruitment(recruitment_id, faction_id)
    if not cancelled:
        await interaction.followup.send(embed=error_embed(
            "Error",
            f"Recruitment #{recruitment_id} not found or does not belong to {display_name}."
        ))
        return

    embed = discord.Embed(
        title=f"Military: {display_name}",
        description=(
            f"Recruitment **#{cancelled['id']}** cancelled.\n"
            f"**{cancelled['amount']:,} {cancelled['role_name']}** will not complete training.\n\n"
            f"*Resources already spent are not refunded.*"
        ),
        color=faction_color
    )
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
