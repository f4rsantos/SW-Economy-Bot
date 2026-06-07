import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import error_embed, success_embed
from services.kanban_service import create_task, upsert_task_assignee
from commands.kanban._utils import (
    board_autocomplete, org_autocomplete, get_board_by_name, get_org_by_name,
    parse_user_ids, PRIORITY_LABELS
)


@app_commands.command(name="add", description="Add a new task to the kanban board")
@app_commands.describe(
    title="Task title",
    board="Board to place the task on",
    description="Task description (optional)",
    org="Organization (optional)",
    priority="Priority level (default: medium)",
    assignees="Mention users or paste IDs separated by spaces (optional)",
)
@app_commands.choices(priority=[
    app_commands.Choice(name="Low",      value="low"),
    app_commands.Choice(name="Medium",   value="medium"),
    app_commands.Choice(name="High",     value="high"),
    app_commands.Choice(name="Critical", value="critical"),
])
@require_access_level(0)
async def add_task_cmd(
    interaction: discord.Interaction,
    title: str,
    board: str,
    description: Optional[str] = None,
    org: Optional[str] = None,
    priority: str = "medium",
    assignees: Optional[str] = None,
):
    await interaction.response.defer()

    if len(title) > 100:
        await interaction.followup.send(embed=error_embed("Error", "Title must be 100 characters or fewer."))
        return
    if description and len(description) > 1000:
        await interaction.followup.send(embed=error_embed("Error", "Description must be 1000 characters or fewer."))
        return

    board_data = await get_board_by_name(board)
    if not board_data:
        await interaction.followup.send(embed=error_embed("Error", f"Board `{board}` not found."))
        return

    org_id = None
    if org:
        org_data = await get_org_by_name(org)
        if not org_data:
            await interaction.followup.send(embed=error_embed("Error", f"Organization `{org}` not found."))
            return
        org_id = org_data['id']

    task_id = await create_task(title, description, board_data['id'], org_id, priority, interaction.user.id)

    assigned_mentions = []
    if assignees:
        user_ids = parse_user_ids(assignees)
        for uid in user_ids:
            await upsert_task_assignee(task_id, uid)
            assigned_mentions.append(f"<@{uid}>")

    lines = [f"**Board:** {board_data['name']}  •  **Priority:** {PRIORITY_LABELS[priority]}"]
    if org:
        lines.append(f"**Org:** {org}")
    if assigned_mentions:
        lines.append(f"**Assigned:** {', '.join(assigned_mentions)}")
    if description:
        lines.append(f"\n{description}")

    embed = success_embed(title=f"Task #{task_id} Created", description="\n".join(lines))
    embed.set_footer(text=f"#{task_id} • {title}")
    await interaction.followup.send(embed=embed)
