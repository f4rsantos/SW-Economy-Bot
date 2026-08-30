# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed
from services.kanban_service import list_task_assignees, list_subtasks
from commands.kanban._utils import get_task, PRIORITY_LABELS, PRIORITY_COLORS


@app_commands.command(name="task", description="View full details of a task")
@app_commands.describe(task_id="Task ID to view")
@require_access_level(0)
async def view_task_cmd(
    interaction: discord.Interaction,
    task_id: int,
):
    await interaction.response.defer()

    task = await get_task(task_id)
    if not task:
        await interaction.followup.send(embed=error_embed("Error", f"Task #{task_id} not found."))
        return

    assignees = await list_task_assignees(task_id)
    subtasks = await list_subtasks(task_id)

    color = PRIORITY_COLORS.get(task.priority, 0x3498db)
    embed = discord.Embed(
        title=f"#{task_id} — {task.title}",
        color=color
    )

    embed.add_field(name="Board",    value=task.board_name,                   inline=True)
    embed.add_field(name="Priority", value=PRIORITY_LABELS[task.priority],    inline=True)
    embed.add_field(name="Org",      value=task.org_name or "—",              inline=True)

    created_ts = int(task.created_at.timestamp())
    updated_ts = int(task.updated_at.timestamp())
    embed.add_field(name="Created", value=f"<@{task.created_by}> <t:{created_ts}:R>", inline=True)
    embed.add_field(name="Updated", value=f"<t:{updated_ts}:R>",                         inline=True)

    if assignees:
        mentions = ", ".join(f"<@{r['user_id']}>" for r in assignees)
        embed.add_field(name=f"Assignees ({len(assignees)})", value=mentions, inline=False)

    if task.description:
        embed.add_field(name="Description", value=task.description[:1024], inline=False)

    if subtasks:
        done_count = sum(1 for s in subtasks if s.done)
        lines = []
        for s in subtasks:
            check = "✅" if s.done else "⬜"
            lines.append(f"{check} `#{s.id}` {s.title}")
        value = "\n".join(lines)
        if len(value) > 1024:
            value = value[:1020] + "\n…"
        embed.add_field(
            name=f"Subtasks ({done_count}/{len(subtasks)} done)",
            value=value,
            inline=False
        )

    embed.set_footer(text=f"Task #{task_id}")
    await interaction.followup.send(embed=embed)
