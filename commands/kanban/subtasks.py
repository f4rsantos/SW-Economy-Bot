import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed, success_embed
from services.kanban_service import (
    next_subtask_position,
    create_subtask,
    get_subtask,
    update_subtask_done,
    touch_task,
)
from commands.kanban._utils import get_task


@app_commands.command(name="subtask-add", description="Add a subtask (checklist item) to a task")
@app_commands.describe(
    task_id="Task ID",
    title="Subtask description",
)
@require_access_level(0)
async def subtask_add_cmd(
    interaction: discord.Interaction,
    task_id: int,
    title: str,
):
    await interaction.response.defer()

    task = await get_task(task_id)
    if not task:
        await interaction.followup.send(embed=error_embed("Error", f"Task #{task_id} not found."))
        return

    if len(title) > 100:
        await interaction.followup.send(embed=error_embed("Error", "Subtask title must be 100 characters or fewer."))
        return

    pos = await next_subtask_position(task_id)
    subtask_id = await create_subtask(task_id, title, pos)
    await touch_task(task_id)

    embed = success_embed(
        title="Subtask Added",
        description=f"⬜ `#{subtask_id}` {title}\nadded to **Task #{task_id} — {task['title']}**"
    )
    await interaction.followup.send(embed=embed)


@app_commands.command(name="subtask-check", description="Mark a subtask as done or not done")
@app_commands.describe(
    task_id="Task ID",
    subtask_id="Subtask ID (shown in /kanban task)",
    done="True to mark done, False to uncheck",
)
@require_access_level(0)
async def subtask_check_cmd(
    interaction: discord.Interaction,
    task_id: int,
    subtask_id: int,
    done: bool,
):
    await interaction.response.defer()

    subtask = await get_subtask(task_id, subtask_id)
    if not subtask:
        await interaction.followup.send(embed=error_embed("Error", f"Subtask #{subtask_id} not found on Task #{task_id}."))
        return

    if subtask['done'] == done:
        state = "already marked as done" if done else "already unchecked"
        await interaction.followup.send(embed=error_embed("No Change", f"Subtask #{subtask_id} is {state}."))
        return

    await update_subtask_done(subtask_id, done)
    await touch_task(task_id)

    check = "✅" if done else "⬜"
    state = "done" if done else "unchecked"
    embed = success_embed(
        title="Subtask Updated",
        description=f"{check} `#{subtask_id}` {subtask['title']} — marked **{state}**"
    )
    await interaction.followup.send(embed=embed)
