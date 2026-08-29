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
from utils.embeds import create_embed
from services.validation_service import require_world
from services import port_service
from repositories import port_repo


@app_commands.command(name="build-lane", description="Build a lane between two of your faction's ports")
@app_commands.describe(
    faction="Faction name",
    port_world_a="World hosting the first port",
    port_world_b="World hosting the second port",
)
@require_access_level(0)
@ephemeral_capable('faction')
async def build_lane(
    interaction: discord.Interaction,
    faction: str,
    port_world_a: str,
    port_world_b: str,
):
    await defer_response(interaction)

    faction_data = await get_faction_by_name(faction)
    if not faction_data:
        await interaction.followup.send(embed=error_embed("Error", f"Faction '{faction}' not found."))
        return

    if not await is_faction_leader(interaction.user.id, faction_data):
        await interaction.followup.send(embed=error_embed("Access Denied", "You must be the faction leader or have admin privileges to build a lane."))
        return

    r_world_a = await require_world(port_world_a)
    if not r_world_a.ok:
        await interaction.followup.send(embed=error_embed("Error", r_world_a.error))
        return
    r_world_b = await require_world(port_world_b)
    if not r_world_b.ok:
        await interaction.followup.send(embed=error_embed("Error", r_world_b.error))
        return

    port_a = await port_repo.get_port_by_world(faction_data.id, r_world_a.data['id'])
    if not port_a:
        await interaction.followup.send(embed=error_embed("Error", f"Your faction has no port on {r_world_a.data['name']}."))
        return
    port_b = await port_repo.get_port_by_world(faction_data.id, r_world_b.data['id'])
    if not port_b:
        await interaction.followup.send(embed=error_embed("Error", f"Your faction has no port on {r_world_b.data['name']}."))
        return

    try:
        result = await port_service.build_lane(faction_data.id, port_a.id, port_b.id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    cost_str = ", ".join(f"{handle_return(cost)} {res}" for res, cost in result['costs'].items())
    embed = success_embed(
        "Lane Constructed",
        f"**{faction_data.display_name}** has built a lane between **{result['port_a_world']}** and **{result['port_b_world']}** for {cost_str}."
    )
    embed.color = hex_to_int(faction_data.color)
    await interaction.followup.send(embed=embed)


@app_commands.command(name="lanes", description="List a faction's ports and lanes")
@app_commands.describe(faction="Faction name")
@require_access_level(0)
async def list_lanes(interaction: discord.Interaction, faction: str):
    faction_data = await get_faction_by_name(faction)
    if not faction_data:
        await interaction.response.send_message(embed=error_embed("Error", f"Faction '{faction}' not found."))
        return

    ports = await port_service.list_faction_ports(faction_data.id)
    lanes = await port_service.list_faction_lanes(faction_data.id)

    if not ports:
        await interaction.response.send_message(
            embed=success_embed("Ports and Lanes", f"**{faction_data.display_name}** has not built any ports yet.")
        )
        return

    port_lines = [f"[{p.id}] {p.world_name}" for p in ports]
    lane_lines = [f"{lane.world_a_name} to {lane.world_b_name}" for lane in lanes]

    fields = [{'name': 'Ports', 'value': "\n".join(port_lines), 'inline': False}]
    if lane_lines:
        fields.append({'name': 'Lanes', 'value': "\n".join(lane_lines), 'inline': False})

    embed = create_embed(
        title=f"{faction_data.display_name} Ports and Lanes",
        color=hex_to_int(faction_data.color),
        fields=fields,
    )
    await interaction.response.send_message(embed=embed)


async def setup(bot):
    pass
