import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed, success_embed
from services.kanban_service import add_task_assignee_if_missing, remove_task_assignee, touch_task
from commands.kanban._utils import get_task, parse_user_ids


@app_commands.command(name="assign", description="Assign users to a task")
@app_commands.describe(
    task_id="Task ID",
    users="Mention users or paste IDs separated by spaces",
)
@require_access_level(0)
async def assign_cmd(
    interaction: discord.Interaction,
    task_id: int,
    users: str,
):
    await interaction.response.defer()

    task = await get_task(task_id)
    if not task:
        await interaction.followup.send(embed=error_embed("Error", f"Task #{task_id} not found."))
        return

    user_ids = parse_user_ids(users)
    if not user_ids:
        await interaction.followup.send(embed=error_embed("Error", "No valid user IDs found. Mention users or paste their IDs."))
        return

    added   = []
    already = []
    for uid in user_ids:
        if await add_task_assignee_if_missing(task_id, uid):
            added.append(uid)
        else:
            already.append(uid)

    await touch_task(task_id)

    lines = [f"**Task #{task_id} — {task['title']}**"]
    if added:
        lines.append("✅ Assigned: " + ", ".join(f"<@{u}>" for u in added))
    if already:
        lines.append("ℹ️ Already assigned: " + ", ".join(f"<@{u}>" for u in already))

    embed = success_embed(title="Assignees Updated", description="\n".join(lines))
    await interaction.followup.send(embed=embed)


@app_commands.command(name="unassign", description="Remove users from a task")
@app_commands.describe(
    task_id="Task ID",
    users="Mention users or paste IDs separated by spaces",
)
@require_access_level(0)
async def unassign_cmd(
    interaction: discord.Interaction,
    task_id: int,
    users: str,
):
    await interaction.response.defer()

    task = await get_task(task_id)
    if not task:
        await interaction.followup.send(embed=error_embed("Error", f"Task #{task_id} not found."))
        return

    user_ids = parse_user_ids(users)
    if not user_ids:
        await interaction.followup.send(embed=error_embed("Error", "No valid user IDs found. Mention users or paste their IDs."))
        return

    removed     = []
    not_assigned = []
    for uid in user_ids:
        if await remove_task_assignee(task_id, uid):
            removed.append(uid)
        else:
            not_assigned.append(uid)

    await touch_task(task_id)

    lines = [f"**Task #{task_id} — {task['title']}**"]
    if removed:
        lines.append("✅ Unassigned: " + ", ".join(f"<@{u}>" for u in removed))
    if not_assigned:
        lines.append("ℹ️ Not assigned: " + ", ".join(f"<@{u}>" for u in not_assigned))

    embed = success_embed(title="Assignees Updated", description="\n".join(lines))
    await interaction.followup.send(embed=embed)
