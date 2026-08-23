# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import error_embed, success_embed
from utils.views import OwnerOnlyView
from services.kanban_service import list_board_ids, count_tasks_for_scope, delete_tasks_for_scope
from commands.kanban._utils import org_autocomplete, get_org_by_name


class ConfirmCleanView(OwnerOnlyView):
    def __init__(self, owner_id: int, scope: str, org_name: str | None,
                 board_ids: list[int], org_id: int | None, preview_count: int):
        super().__init__(owner_id=owner_id, timeout=60)
        self.scope         = scope
        self.org_name      = org_name
        self.board_ids     = board_ids
        self.org_id        = org_id
        self.preview_count = preview_count

    @discord.ui.button(label="Confirm Clean", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        deleted = await delete_tasks_for_scope(self.board_ids, self.org_id)

        for child in self.children:
            child.disabled = True
        self.stop()

        scope_str = self.scope.replace("_", " ").title()
        org_str   = f" in **{self.org_name}**" if self.org_name else ""
        embed = success_embed(
            title="Kanban Cleaned",
            description=f"Removed **{deleted}** task(s) from {scope_str}{org_str}."
        )
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        for child in self.children:
            child.disabled = True
        self.stop()
        await interaction.response.edit_message(
            embed=discord.Embed(description="Clean cancelled.", color=0x95a5a6),
            view=self
        )


@app_commands.command(name="clean", description="Bulk-remove tasks from the board")
@app_commands.describe(
    scope="Which tasks to remove",
    org="Limit to a specific organization (optional)",
)
@app_commands.choices(scope=[
    app_commands.Choice(name="Done only",  value="done"),
    app_commands.Choice(name="All tasks",  value="all"),
])
@require_access_level(4)
async def clean_cmd(
    interaction: discord.Interaction,
    scope: str,
    org: Optional[str] = None,
):
    await interaction.response.defer()

    org_id   = None
    org_name = None
    if org:
        org_data = await get_org_by_name(org)
        if not org_data:
            await interaction.followup.send(
                embed=error_embed("Error", f"Organization `{org}` not found."),
            )
            return
        org_id   = org_data.id
        org_name = org_data.name

    board_ids = await list_board_ids(scope)
    if not board_ids:
        await interaction.followup.send(
            embed=error_embed("Error", "No matching boards found."),
        )
        return

    count = await count_tasks_for_scope(board_ids, org_id)

    if count == 0:
        await interaction.followup.send(
            embed=discord.Embed(description="No tasks match that selection.", color=0x95a5a6),
        )
        return

    scope_str = "Done board" if scope == "done" else "all boards"
    org_str   = f" in **{org_name}**" if org_name else ""
    embed = discord.Embed(
        title="Confirm Clean",
        description=(
            f"This will permanently delete **{count}** task(s) "
            f"from {scope_str}{org_str}.\n\n"
            "This cannot be undone."
        ),
        color=0xe74c3c
    )

    view = ConfirmCleanView(
        owner_id=interaction.user.id,
        scope=scope,
        org_name=org_name,
        board_ids=board_ids,
        org_id=org_id,
        preview_count=count,
    )
    await interaction.followup.send(embed=embed, view=view)
