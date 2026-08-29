# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from services.user_service import (
    get_user_access_level,
    get_pending_allegiance_requests,
    approve_allegiance_request,
    deny_allegiance_request,
)
from services.faction_service import get_faction_row_by_id
from services.validation_service import require_faction


async def _can_manage_faction(user_id: int, faction_id: int) -> bool:
    if await get_user_access_level(user_id) >= 4:
        return True
    faction = await get_faction_row_by_id(faction_id)
    return faction is not None and faction.leader_id == user_id


@app_commands.command(name="allegiance-requests", description="View pending allegiance requests for a faction")
@app_commands.describe(faction="Name or ID of the faction")
@require_access_level(0)
async def allegiance_requests(interaction: discord.Interaction, faction: str):
    await interaction.response.defer(ephemeral=True)

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok:
        return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    if not await _can_manage_faction(interaction.user.id, faction_data.id):
        await interaction.followup.send(embed=error_embed("Access Denied", "You must be the faction leader or have admin privileges to view this faction's allegiance requests."))
        return

    pending = await get_pending_allegiance_requests(faction_data.id)
    if not pending:
        await interaction.followup.send(embed=success_embed(title="Allegiance Requests", description=f"**{faction_data.display_name}** has no pending allegiance requests."))
        return

    lines = [f"`#{r.id}` <@{r.user_id}>, requested <t:{int(r.requested_at.timestamp())}:R>" for r in pending]
    embed = success_embed(
        title="Pending Allegiance Requests",
        description=f"**{faction_data.display_name}**\n\n" + "\n".join(lines) + "\n\nUse /faction allegiance-decide to approve or deny."
    )
    await interaction.followup.send(embed=embed)


@app_commands.command(name="allegiance-decide", description="Approve or deny a pending allegiance request")
@app_commands.describe(request_id="The request ID shown in /faction allegiance-requests", approve="Approve the request, or deny it")
@require_access_level(0)
async def allegiance_decide(interaction: discord.Interaction, request_id: int, approve: bool):
    await interaction.response.defer(ephemeral=True)

    from repositories import allegiance_repo
    request = await allegiance_repo.get_request_by_id(request_id)
    if request is None:
        await interaction.followup.send(embed=error_embed("Error", f"No allegiance request with ID {request_id} was found."))
        return

    if not await _can_manage_faction(interaction.user.id, request.faction_id):
        await interaction.followup.send(embed=error_embed("Access Denied", "You must be the faction leader or have admin privileges to decide this request."))
        return

    faction_data = await get_faction_row_by_id(request.faction_id)
    faction_display = faction_data.display_name if faction_data else "this faction"

    if request.status != "pending":
        await interaction.followup.send(embed=error_embed("Error", "This request has already been resolved."))
        return

    try:
        if approve:
            await approve_allegiance_request(request_id, interaction.user.id, faction_display)
        else:
            await deny_allegiance_request(request_id, interaction.user.id, faction_display)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    action = "Approved" if approve else "Denied"
    embed = success_embed(
        title=f"Allegiance Request {action}",
        description=f"The allegiance request from <@{request.user_id}> to **{faction_display}** has been {action.lower()}."
    )
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
