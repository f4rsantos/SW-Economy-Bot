import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import error_embed, success_embed
from services.kanban_service import (
    org_exists,
    create_org,
    get_org_by_name,
    delete_org_and_unlink_tasks,
    list_orgs_with_task_count,
    list_boards_with_task_count,
)


@app_commands.command(name="add-org", description="Create a new kanban organization")
@app_commands.describe(name="Organization name")
@require_access_level(0)
async def add_org_cmd(
    interaction: discord.Interaction,
    name: str,
):
    await interaction.response.defer()

    if len(name) > 80:
        await interaction.followup.send(embed=error_embed("Error", "Organization name must be 80 characters or fewer."))
        return

    if await org_exists(name):
        await interaction.followup.send(embed=error_embed("Error", f"Organization `{name}` already exists."))
        return

    org_id = await create_org(name)
    embed = success_embed(title="Organization Created", description=f"**{name}** (ID: {org_id})")
    await interaction.followup.send(embed=embed)


@app_commands.command(name="remove-org", description="Remove a kanban organization")
@app_commands.describe(name="Organization name")
@require_access_level(0)
async def remove_org_cmd(
    interaction: discord.Interaction,
    name: str,
):
    await interaction.response.defer()

    org = await get_org_by_name(name)
    if not org:
        await interaction.followup.send(embed=error_embed("Error", f"Organization `{name}` not found."))
        return

    await delete_org_and_unlink_tasks(org['id'])

    embed = success_embed(title="Organization Removed", description=f"**{name}** has been removed. Tasks were unlinked.")
    await interaction.followup.send(embed=embed)


@app_commands.command(name="orgs", description="List all kanban organizations")
@require_access_level(0)
async def list_orgs_cmd(interaction: discord.Interaction):
    await interaction.response.defer()

    orgs = await list_orgs_with_task_count()

    if not orgs:
        embed = discord.Embed(title="Organizations", description="No organizations created yet.", color=0x3498db)
        await interaction.followup.send(embed=embed)
        return

    lines = [f"**{o['name']}** — {o['task_count']} task(s)  `ID: {o['id']}`" for o in orgs]
    embed = discord.Embed(
        title=f"Organizations ({len(orgs)})",
        description="\n".join(lines),
        color=0x3498db
    )
    await interaction.followup.send(embed=embed)


@app_commands.command(name="boards", description="List all kanban boards with task counts")
@require_access_level(0)
async def list_boards_cmd(interaction: discord.Interaction):
    await interaction.response.defer()

    rows = await list_boards_with_task_count()

    embed = discord.Embed(title="Kanban Boards", color=0x3498db)
    for r in rows:
        embed.add_field(
            name=f"{r['position'] + 1}. {r['name']}",
            value=f"{r['task_count']} task(s)",
            inline=True
        )
    await interaction.followup.send(embed=embed)
