# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import create_embed, success_embed, error_embed
from utils.faction_utils import hex_to_int, get_faction_by_name
from services import megaproject_service


@app_commands.command(name="list", description="List a faction's megaprojects")
@app_commands.describe(faction="Faction name")
@require_access_level(0)
async def list_megaprojects(interaction: discord.Interaction, faction: str):
    faction_data = await get_faction_by_name(faction)
    if not faction_data:
        await interaction.response.send_message(embed=error_embed("Error", f"Faction '{faction}' not found."))
        return

    projects = await megaproject_service.list_faction_megaprojects(faction_data.id)

    if not projects:
        await interaction.response.send_message(
            embed=success_embed("Megaprojects", f"**{faction_data.display_name}** has not built any megaprojects yet.")
        )
        return

    lines = []
    for project in projects:
        status = "Active" if project.is_active else "Disabled"
        location = f" on {project.world_name}" if project.world_name else ""
        lines.append(f"[{project.id}] {project.type_name}{location} — {status}")

    embed = create_embed(
        title=f"{faction_data.display_name} Megaprojects",
        description="\n".join(lines),
        color=hex_to_int(faction_data.color),
    )
    await interaction.response.send_message(embed=embed)


async def setup(bot):
    pass
