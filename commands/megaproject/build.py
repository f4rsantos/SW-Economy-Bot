# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int, get_faction_by_name, is_faction_leader
from services.validation_service import require_world
from services import megaproject_service, port_service

PROJECT_CHOICES = [
    app_commands.Choice(name="Terraformer", value=megaproject_service.TERRAFORMER),
    app_commands.Choice(name="Resource Recycling Center", value=megaproject_service.RECYCLING_CENTER),
    app_commands.Choice(name="Extractors Upgrade", value=megaproject_service.EXTRACTORS_UPGRADE),
    app_commands.Choice(name="Interplanetary Port", value=port_service.INTERPLANETARY_PORT),
]


@app_commands.command(name="build", description="Build a megaproject for your faction")
@app_commands.describe(
    faction="Faction name",
    project="Megaproject type",
    world="World name (required for Terraformer and Interplanetary Port)",
)
@app_commands.choices(project=PROJECT_CHOICES)
@require_access_level(0)
@ephemeral_capable('faction')
async def build_megaproject(
    interaction: discord.Interaction,
    faction: str,
    project: app_commands.Choice[str],
    world: str = None,
):
    await defer_response(interaction)

    faction_data = await get_faction_by_name(faction)
    if not faction_data:
        await interaction.followup.send(embed=error_embed("Error", f"Faction '{faction}' not found."))
        return

    if not await is_faction_leader(interaction.user.id, faction_data):
        await interaction.followup.send(embed=error_embed("Access Denied", "You must be the faction leader or have admin privileges to build a megaproject."))
        return

    faction_id = faction_data.id
    faction_color = hex_to_int(faction_data.color)
    project_code = project.value

    try:
        if project_code == megaproject_service.TERRAFORMER:
            if not world:
                await interaction.followup.send(embed=error_embed("Error", "A world is required to build a Terraformer."))
                return
            r_world = await require_world(world)
            if not r_world.ok:
                await interaction.followup.send(embed=error_embed("Error", r_world.error))
                return
            world_data = r_world.data
            result = await megaproject_service.build_terraformer(faction_id, world_data['id'], world_data['name'])
            cost_str = ", ".join(f"{handle_return(cost)} {res}" for res, cost in result['costs'].items())
            embed = success_embed(
                "Terraformer Constructed",
                f"**{faction_data.display_name}** has built a Terraformer on **{world_data['name']}** for {cost_str}."
            )
            embed.add_field(name="Forward To Mapping Corps", value=result['forward_message'], inline=False)
        elif project_code == megaproject_service.RECYCLING_CENTER:
            result = await megaproject_service.build_recycling_center(faction_id)
            cost_str = ", ".join(f"{handle_return(cost)} {res}" for res, cost in result['costs'].items())
            embed = success_embed(
                "Resource Recycling Center Constructed",
                f"**{faction_data.display_name}** has built a Resource Recycling Center for {cost_str}."
            )
        elif project_code == megaproject_service.EXTRACTORS_UPGRADE:
            result = await megaproject_service.build_extractors_upgrade(faction_id)
            cost_str = ", ".join(f"{handle_return(cost)} {res}" for res, cost in result['costs'].items())
            embed = success_embed(
                "Extractors Upgrade Constructed",
                f"**{faction_data.display_name}** has upgraded its extractors for {cost_str}."
            )
        elif project_code == port_service.INTERPLANETARY_PORT:
            if not world:
                await interaction.followup.send(embed=error_embed("Error", "A world is required to build an Interplanetary Port."))
                return
            r_world = await require_world(world)
            if not r_world.ok:
                await interaction.followup.send(embed=error_embed("Error", r_world.error))
                return
            world_data = r_world.data
            result = await port_service.build_port(faction_id, world_data['id'], world_data['name'])
            cost_str = ", ".join(f"{handle_return(cost)} {res}" for res, cost in result['costs'].items())
            embed = success_embed(
                "Interplanetary Port Constructed",
                f"**{faction_data.display_name}** has built an Interplanetary Port on **{world_data['name']}** for {cost_str}."
            )
        else:
            await interaction.followup.send(embed=error_embed("Error", "Unknown megaproject type."))
            return
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
