# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import success_embed, error_embed
from utils.currency import parse_currency, handle_return
from utils.faction_utils import hex_to_int, get_faction_by_name, is_faction_leader
from services.validation_service import require_world
from services import megaproject_service

PROJECT_CHOICES = [
    app_commands.Choice(name="Terraformer", value=megaproject_service.TERRAFORMER),
    app_commands.Choice(name="Resource Recycling Center", value=megaproject_service.RECYCLING_CENTER),
    app_commands.Choice(name="Extractors Upgrade", value=megaproject_service.EXTRACTORS_UPGRADE),
]


@app_commands.command(name="contribute", description="Contribute resources toward an in-progress megaproject")
@app_commands.describe(
    faction="Faction name",
    project="Megaproject type",
    resources="Resources to contribute, e.g. 10k CM, 5 mil ER",
    world="World name (required for Terraformer)",
)
@app_commands.choices(project=PROJECT_CHOICES)
@require_access_level(0)
@ephemeral_capable('faction')
async def contribute_megaproject(
    interaction: discord.Interaction,
    faction: str,
    project: app_commands.Choice[str],
    resources: str,
    world: str = None,
):
    await defer_response(interaction)

    faction_data = await get_faction_by_name(faction)
    if not faction_data:
        await interaction.followup.send(embed=error_embed("Error", f"Faction '{faction}' not found."))
        return

    if not await is_faction_leader(interaction.user.id, faction_data):
        await interaction.followup.send(embed=error_embed("Access Denied", "You must be the faction leader or have admin privileges to contribute to a megaproject."))
        return

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)
    project_code = project.value

    world_id = None
    world_name = None
    if project_code == megaproject_service.TERRAFORMER:
        if not world:
            await interaction.followup.send(embed=error_embed("Error", "A world is required to contribute to a Terraformer."))
            return
        r_world = await require_world(world)
        if not r_world.ok:
            await interaction.followup.send(embed=error_embed("Error", r_world.error))
            return
        world_data = r_world.data
        world_id = world_data['id']
        world_name = world_data['name']

    try:
        parsed = parse_currency(resources)
    except ValueError:
        await interaction.followup.send(embed=error_embed("Error", "Could not parse the resources provided."))
        return

    contributions = {}
    for entry in parsed:
        contributions[entry['resource']] = contributions.get(entry['resource'], 0) + entry['amount']

    try:
        result = await megaproject_service.contribute_to_megaproject(faction_id, project_code, world_id, contributions)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    contributed_str = ", ".join(f"{handle_return(amount)} {res}" for res, amount in result['contributed'].items())

    if result['completed']:
        target_name = world_name or faction_data.display_name
        embed = success_embed(
            "Megaproject Completed",
            f"**{faction_data.display_name}** contributed {contributed_str} and completed **{project.name}** on **{target_name}**." if world_name
            else f"**{faction_data.display_name}** contributed {contributed_str} and completed **{project.name}**."
        )
    else:
        progress_lines = []
        for res, target in result['targets'].items():
            current = result['progress'].get(res, 0)
            progress_lines.append(f"{res}: {handle_return(current)} / {handle_return(target)}")
        embed = success_embed(
            "Contribution Recorded",
            f"**{faction_data.display_name}** contributed {contributed_str} toward **{project.name}**."
        )
        embed.add_field(name="Progress", value="\n".join(progress_lines), inline=False)

    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
