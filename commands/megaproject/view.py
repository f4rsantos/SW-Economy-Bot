# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import create_embed, error_embed
from utils.faction_utils import hex_to_int, get_faction_by_name
from services import megaproject_service


@app_commands.command(name="view", description="View details of a faction's megaproject")
@app_commands.describe(faction="Faction name", project_id="Megaproject ID (from /megaproject list)")
@require_access_level(0)
async def view_megaproject(interaction: discord.Interaction, faction: str, project_id: int):
    faction_data = await get_faction_by_name(faction)
    if not faction_data:
        await interaction.response.send_message(embed=error_embed("Error", f"Faction '{faction}' not found."))
        return

    project = await megaproject_service.get_megaproject_detail(faction_data.id, project_id)
    if not project:
        await interaction.response.send_message(embed=error_embed("Error", "Megaproject not found for this faction."))
        return

    status = "Active" if project.is_active else "Disabled"
    fields = [
        {'name': 'Type', 'value': project.type_name, 'inline': True},
        {'name': 'Status', 'value': status, 'inline': True},
        {'name': 'Built', 'value': f"<t:{int(project.built_at.timestamp())}:R>", 'inline': True},
    ]
    if project.world_name:
        fields.append({'name': 'World', 'value': project.world_name, 'inline': True})
    if project.disabled_at:
        fields.append({'name': 'Disabled', 'value': f"<t:{int(project.disabled_at.timestamp())}:R>", 'inline': True})

    embed = create_embed(
        title=f"Megaproject #{project.id}",
        color=hex_to_int(faction_data.color),
        fields=fields,
    )
    await interaction.response.send_message(embed=embed)


async def setup(bot):
    pass
