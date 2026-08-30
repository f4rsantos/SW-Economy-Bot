# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from utils.views import RecruitmentPaginatorView
from services.recruit_service import get_pending_recruitments
from services.validation_service import require_faction


@app_commands.command(name="progress", description="Check pending military recruitments")
@app_commands.describe(faction="Faction name")
@require_access_level(0)
@ephemeral_capable('faction')
async def progress(interaction: discord.Interaction, faction: str):
    await defer_response(interaction)

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    pending = await get_pending_recruitments(faction_data.id)
    faction_color = hex_to_int(faction_data.color)
    display_name = faction_data.display_name

    if not pending:
        await interaction.followup.send(embed=discord.Embed(
            title=f"Recruitments: {display_name}",
            description="No pending recruitments.",
            color=faction_color
        ))
        return

    total = sum(r.amount for r in pending)
    title = f"{display_name}'s Recruitments"
    view = RecruitmentPaginatorView(interaction.user.id, title, faction_color, pending, total)
    embed = view.build_embed()

    if view.max_page == 0:
        await interaction.followup.send(embed=embed)
    else:
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    pass
