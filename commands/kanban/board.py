# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.views import OwnerOnlyView
from services.kanban_service import list_board_tasks
from commands.kanban._utils import (
    board_autocomplete, org_autocomplete, get_board_by_name, get_org_by_name,
    PRIORITY_LABELS
)

TASKS_PER_PAGE = 8


def _build_board_embed(board_data, tasks, page: int, total_pages: int, org_name: str = None, priority: str = None) -> discord.Embed:
    filter_parts = []
    if org_name:
        filter_parts.append(f"Org: {org_name}")
    if priority:
        filter_parts.append(f"Priority: {PRIORITY_LABELS[priority]}")
    title = f"{board_data.name} Board"
    if filter_parts:
        title += f"  ({', '.join(filter_parts)})"

    embed = discord.Embed(title=title, color=board_data.color)

    if not tasks:
        embed.description = "No tasks on this board."
    else:
        for t in tasks:
            assignee_count = t.assignee_count
            org_str    = f" • {t.org_name}" if t.org_name else ""
            assign_str = f" • {assignee_count} assigned" if assignee_count else ""
            embed.add_field(
                name=f"#{t.id} {t.title}",
                value=f"{PRIORITY_LABELS[t.priority]}{org_str}{assign_str}",
                inline=False
            )

    embed.set_footer(text=f"Page {page}/{total_pages} • {board_data.name}")
    return embed


class BoardView(OwnerOnlyView):
    def __init__(self, owner_id: int, board_data, all_tasks: list, org_name: str = None, priority: str = None):
        super().__init__(owner_id=owner_id, timeout=120)
        self.board_data = board_data
        self.all_tasks  = all_tasks
        self.org_name   = org_name
        self.priority   = priority
        self.page       = 1
        self.total_pages = max(1, -(-len(all_tasks) // TASKS_PER_PAGE))
        self._update_buttons()

    def _page_tasks(self):
        start = (self.page - 1) * TASKS_PER_PAGE
        return self.all_tasks[start:start + TASKS_PER_PAGE]

    def _update_buttons(self):
        self.prev_btn.disabled = self.page <= 1
        self.next_btn.disabled = self.page >= self.total_pages

    def build_embed(self):
        return _build_board_embed(
            self.board_data, self._page_tasks(),
            self.page, self.total_pages,
            self.org_name, self.priority
        )

    @discord.ui.button(label="◀ Prev", style=discord.ButtonStyle.secondary)
    async def prev_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page -= 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary)
    async def next_btn(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page += 1
        self._update_buttons()
        await interaction.response.edit_message(embed=self.build_embed(), view=self)


@app_commands.command(name="board", description="View tasks on a specific board")
@app_commands.describe(
    name="Board name",
    org="Filter by organization (optional)",
    priority="Filter by priority (optional)",
)
@app_commands.choices(priority=[
    app_commands.Choice(name="Low",      value="low"),
    app_commands.Choice(name="Medium",   value="medium"),
    app_commands.Choice(name="High",     value="high"),
    app_commands.Choice(name="Critical", value="critical"),
])
@require_access_level(0)
async def board_cmd(
    interaction: discord.Interaction,
    name: str,
    org: Optional[str] = None,
    priority: Optional[str] = None,
):
    await interaction.response.defer()

    board_data = await get_board_by_name(name)
    if not board_data:
        await interaction.followup.send(embed=error_embed("Error", f"Board `{name}` not found."))
        return

    org_id = None
    org_name = None
    if org:
        org_data = await get_org_by_name(org)
        if not org_data:
            await interaction.followup.send(embed=error_embed("Error", f"Organization `{org}` not found."))
            return
        org_id   = org_data.id
        org_name = org_data.name

    tasks = await list_board_tasks(board_data.id, org_id=org_id, priority=priority)
    view  = BoardView(interaction.user.id, board_data, tasks, org_name, priority)
    await interaction.followup.send(embed=view.build_embed(), view=view)
