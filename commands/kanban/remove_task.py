# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed, success_embed
from utils.views import OwnerOnlyView
from services.kanban_service import delete_task, count_subtasks
from commands.kanban._utils import get_task


class ConfirmDeleteView(OwnerOnlyView):
    def __init__(self, owner_id: int, task_id: int, task_title: str):
        super().__init__(owner_id=owner_id, timeout=60)
        self.task_id    = task_id
        self.task_title = task_title

    @discord.ui.button(label="Delete", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await delete_task(self.task_id)
        for child in self.children:
            child.disabled = True
        self.stop()
        embed = success_embed(
            title="Task Deleted",
            description=f"Task **#{self.task_id} — {self.task_title}** has been permanently removed."
        )
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        self.stop()
        embed = discord.Embed(description="Deletion cancelled.", color=0x95a5a6)
        await interaction.response.edit_message(embed=embed, view=self)


@app_commands.command(name="remove", description="Remove a task from the board")
@app_commands.describe(task_id="Task ID to remove")
@require_access_level(0)
async def remove_task_cmd(
    interaction: discord.Interaction,
    task_id: int,
):
    await interaction.response.defer()

    task = await get_task(task_id)
    if not task:
        await interaction.followup.send(embed=error_embed("Error", f"Task #{task_id} not found."))
        return

    subtask_count = await count_subtasks(task_id)

    lines = [f"**#{task_id} — {task.title}**", f"Board: {task.board_name}"]
    if subtask_count:
        lines.append(f"This will also delete **{subtask_count}** subtask(s).")

    embed = discord.Embed(
        title="Confirm Deletion",
        description="\n".join(lines),
        color=0xe74c3c
    )
    view = ConfirmDeleteView(interaction.user.id, task_id, task.title)
    await interaction.followup.send(embed=embed, view=view)
