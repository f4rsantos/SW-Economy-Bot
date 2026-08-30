# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import error_embed
from services.kanban_service import list_boards, board_task_counts, board_task_preview_rows
from commands.kanban._utils import org_autocomplete, get_org_by_name, PRIORITY_LABELS

PREVIEW_TASKS = 3


@app_commands.command(name="overview", description="View a summary of all kanban boards")
@app_commands.describe(org="Filter by organization (optional)")
@require_access_level(0)
async def overview_cmd(
    interaction: discord.Interaction,
    org: Optional[str] = None,
):
    await interaction.response.defer()

    org_id   = None
    org_name = None
    if org:
        org_data = await get_org_by_name(org)
        if not org_data:
            await interaction.followup.send(embed=error_embed("Error", f"Organization `{org}` not found."))
            return
        org_id   = org_data.id
        org_name = org_data.name

    boards = await list_boards()
    count_map = await board_task_counts(org_id=org_id)
    task_rows = await board_task_preview_rows(org_id=org_id)
    tasks_by_board: dict[int, list] = {}
    for t in task_rows:
        tasks_by_board.setdefault(t['board_id'], []).append(t)

    title = "Kanban Overview"
    if org_name:
        title += f" — {org_name}"

    total_tasks = sum(count_map.values()) if count_map else 0
    embed = discord.Embed(
        title=title,
        description=f"**{total_tasks}** task(s) across {len(boards)} boards",
        color=0x3498db
    )

    for board in boards:
        bid   = board.id
        cnt   = count_map.get(bid, 0)
        tasks = tasks_by_board.get(bid, [])

        if cnt == 0:
            value = "*Empty*"
        else:
            previews = []
            for t in tasks[:PREVIEW_TASKS]:
                previews.append(f"`#{t['id']}` {t['title'][:40]}")
            value = "\n".join(previews)
            if cnt > PREVIEW_TASKS:
                value += f"\n*…and {cnt - PREVIEW_TASKS} more*"

        embed.add_field(
            name=f"{board.name}  ({cnt})",
            value=value,
            inline=False
        )

    await interaction.followup.send(embed=embed)
