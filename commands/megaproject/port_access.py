# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import success_embed, error_embed, create_embed
from utils.faction_utils import hex_to_int, get_faction_by_name, is_faction_leader
from services.validation_service import require_world
from services import port_service
from repositories import port_repo

TRAFFIC_CHOICES = [
    app_commands.Choice(name="Transfers", value=port_service.TRAFFIC_TRANSFERS),
    app_commands.Choice(name="Units", value=port_service.TRAFFIC_UNITS),
]

POLICY_CHOICES = [
    app_commands.Choice(name="Allow", value=port_service.POLICY_ALLOW),
    app_commands.Choice(name="Deny", value=port_service.POLICY_DENY),
]


async def _resolve_port(faction_name: str, port_world: str):
    faction_data = await get_faction_by_name(faction_name)
    if not faction_data:
        return None, error_embed("Error", f"Faction '{faction_name}' not found.")

    r_world = await require_world(port_world)
    if not r_world.ok:
        return None, error_embed("Error", r_world.error)

    port = await port_repo.get_port_by_world(faction_data.id, r_world.data['id'])
    if not port:
        return None, error_embed("Error", f"'{faction_name}' has no port on {r_world.data['name']}.")

    return (faction_data, port), None


@app_commands.command(name="port-access-set", description="Set who may use your port for transfers or units")
@app_commands.describe(
    faction="Your faction name",
    port_world="World hosting your port",
    traffic="Transfers or units",
    policy="Allow or deny",
    other_faction="Faction the rule applies to, leave empty for everyone else",
)
@app_commands.choices(traffic=TRAFFIC_CHOICES, policy=POLICY_CHOICES)
@require_access_level(0)
@ephemeral_capable('faction')
async def port_access_set(
    interaction: discord.Interaction,
    faction: str,
    port_world: str,
    traffic: app_commands.Choice[str],
    policy: app_commands.Choice[str],
    other_faction: str = None,
):
    await defer_response(interaction)

    resolved, err = await _resolve_port(faction, port_world)
    if err:
        await interaction.followup.send(embed=err)
        return
    faction_data, port = resolved

    if not await is_faction_leader(interaction.user.id, faction_data):
        await interaction.followup.send(embed=error_embed("Access Denied", "You must be the faction leader or have admin privileges to manage port access."))
        return

    other_faction_id = None
    other_faction_label = "everyone else"
    if other_faction:
        other_faction_data = await get_faction_by_name(other_faction)
        if not other_faction_data:
            await interaction.followup.send(embed=error_embed("Error", f"Faction '{other_faction}' not found."))
            return
        other_faction_id = other_faction_data.id
        other_faction_label = other_faction_data.display_name

    try:
        await port_service.set_access_rule_for_port(faction_data.id, port.id, traffic.value, policy.value, other_faction_id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    policy_label = "allowed" if policy.value == port_service.POLICY_ALLOW else "denied"
    embed = success_embed(
        "Port Access Rule Set",
        f"{other_faction_label} will now be **{policy_label}** for **{traffic.value}** through the port on **{port.world_name}**."
    )
    embed.color = hex_to_int(faction_data.color)
    await interaction.followup.send(embed=embed)


@app_commands.command(name="port-access-clear", description="Remove a port access rule, reverting to the default")
@app_commands.describe(
    faction="Your faction name",
    port_world="World hosting your port",
    traffic="Transfers or units",
    other_faction="Faction the rule applies to, leave empty for the default policy",
)
@app_commands.choices(traffic=TRAFFIC_CHOICES)
@require_access_level(0)
@ephemeral_capable('faction')
async def port_access_clear(
    interaction: discord.Interaction,
    faction: str,
    port_world: str,
    traffic: app_commands.Choice[str],
    other_faction: str = None,
):
    await defer_response(interaction)

    resolved, err = await _resolve_port(faction, port_world)
    if err:
        await interaction.followup.send(embed=err)
        return
    faction_data, port = resolved

    if not await is_faction_leader(interaction.user.id, faction_data):
        await interaction.followup.send(embed=error_embed("Access Denied", "You must be the faction leader or have admin privileges to manage port access."))
        return

    other_faction_id = None
    if other_faction:
        other_faction_data = await get_faction_by_name(other_faction)
        if not other_faction_data:
            await interaction.followup.send(embed=error_embed("Error", f"Faction '{other_faction}' not found."))
            return
        other_faction_id = other_faction_data.id

    try:
        cleared = await port_service.clear_access_rule_for_port(faction_data.id, port.id, traffic.value, other_faction_id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    if not cleared:
        await interaction.followup.send(embed=error_embed("Error", "No matching rule was found to clear."))
        return

    embed = success_embed("Port Access Rule Cleared", f"The rule has been removed from the port on **{port.world_name}**.")
    embed.color = hex_to_int(faction_data.color)
    await interaction.followup.send(embed=embed)


@app_commands.command(name="port-access-list", description="List access rules for a port")
@app_commands.describe(faction="Faction name", port_world="World hosting the port")
@require_access_level(0)
async def port_access_list(interaction: discord.Interaction, faction: str, port_world: str):
    resolved, err = await _resolve_port(faction, port_world)
    if err:
        await interaction.response.send_message(embed=err)
        return
    faction_data, port = resolved

    rules = await port_service.list_access_rules_for_port(faction_data.id, port.id)
    if not rules:
        await interaction.response.send_message(
            embed=success_embed("Port Access Rules", f"No rules set for the port on **{port.world_name}**. Everyone may use it.")
        )
        return

    lines = []
    for rule in rules:
        target = rule.faction_name if rule.faction_id else "Everyone else"
        lines.append(f"{target}: {rule.policy} {rule.traffic_type}")

    embed = create_embed(
        title=f"Port Access Rules on {port.world_name}",
        description="\n".join(lines),
        color=hex_to_int(faction_data.color),
    )
    await interaction.response.send_message(embed=embed)


async def setup(bot):
    pass
