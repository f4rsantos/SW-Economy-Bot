# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import create_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int, get_faction_by_name
from services.validation_service import require_world
from services import megaproject_service

PROGRESS_CHOICES = [
    app_commands.Choice(name="Terraformer", value=megaproject_service.TERRAFORMER),
    app_commands.Choice(name="Resource Recycling Center", value=megaproject_service.RECYCLING_CENTER),
    app_commands.Choice(name="Extractors Upgrade", value=megaproject_service.EXTRACTORS_UPGRADE),
]


@app_commands.command(name="view", description="View details of a faction's megaproject")
@app_commands.describe(faction="Faction name", project_id="Megaproject ID (from /megaproject list)")
@require_access_level(0)
async def view_megaproject(interaction: discord.Interaction, faction: str, project_id: int):
    await interaction.response.defer()
    faction_data = await get_faction_by_name(faction)
    if not faction_data:
        await interaction.followup.send(embed=error_embed("Error", f"Faction '{faction}' not found."))
        return

    project = await megaproject_service.get_megaproject_detail(faction_data.id, project_id)
    if not project:
        await interaction.followup.send(embed=error_embed("Error", "Megaproject not found for this faction."))
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
    await interaction.followup.send(embed=embed)


@app_commands.command(name="progress", description="View a faction's in-progress megaproject contributions")
@app_commands.describe(
    faction="Faction name",
    project="Megaproject type",
    world="World name (required for Terraformer)",
)
@app_commands.choices(project=PROGRESS_CHOICES)
@require_access_level(0)
async def view_megaproject_progress(
    interaction: discord.Interaction,
    faction: str,
    project: app_commands.Choice[str],
    world: str = None,
):
    await interaction.response.defer()
    faction_data = await get_faction_by_name(faction)
    if not faction_data:
        await interaction.followup.send(embed=error_embed("Error", f"Faction '{faction}' not found."))
        return

    world_id = None
    if project.value == megaproject_service.TERRAFORMER:
        if not world:
            await interaction.followup.send(embed=error_embed("Error", "A world is required to view Terraformer progress."))
            return
        r_world = await require_world(world)
        if not r_world.ok:
            await interaction.followup.send(embed=error_embed("Error", r_world.error))
            return
        world_id = r_world.data['id']

    try:
        result = await megaproject_service.get_megaproject_progress(faction_data.id, project.value, world_id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    progress_lines = []
    for res, target in result['targets'].items():
        current = result['progress'].get(res, 0)
        progress_lines.append(f"{res}: {handle_return(current)} / {handle_return(target)}")

    status = "Complete" if result['completed'] else "In Progress"
    embed = create_embed(
        title=f"{project.name} Progress",
        color=hex_to_int(faction_data.color),
        fields=[
            {'name': 'Status', 'value': status, 'inline': False},
            {'name': 'Progress', 'value': "\n".join(progress_lines) or "No contributions yet.", 'inline': False},
        ],
    )
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
