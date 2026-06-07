import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import error_embed, success_embed
from services.kanban_service import update_task
from commands.kanban._utils import org_autocomplete, get_task, get_org_by_name, PRIORITY_LABELS


@app_commands.command(name="edit", description="Edit an existing task")
@app_commands.describe(
    task_id="Task ID to edit",
    title="New title (optional)",
    description="New description (optional)",
    priority="New priority (optional)",
    org="New organization (optional, use 'none' to clear)",
)
@app_commands.choices(priority=[
    app_commands.Choice(name="Low",      value="low"),
    app_commands.Choice(name="Medium",   value="medium"),
    app_commands.Choice(name="High",     value="high"),
    app_commands.Choice(name="Critical", value="critical"),
])
@require_access_level(0)
async def edit_task_cmd(
    interaction: discord.Interaction,
    task_id: int,
    title: Optional[str] = None,
    description: Optional[str] = None,
    priority: Optional[str] = None,
    org: Optional[str] = None,
):
    await interaction.response.defer()

    task = await get_task(task_id)
    if not task:
        await interaction.followup.send(embed=error_embed("Error", f"Task #{task_id} not found."))
        return

    if title and len(title) > 100:
        await interaction.followup.send(embed=error_embed("Error", "Title must be 100 characters or fewer."))
        return
    if description and len(description) > 1000:
        await interaction.followup.send(embed=error_embed("Error", "Description must be 1000 characters or fewer."))
        return

    new_title       = title       if title       is not None else task['title']
    new_description = description if description is not None else task['description']
    new_priority    = priority    if priority    is not None else task['priority']

    new_org_id = task['org_id']
    if org is not None:
        if org.lower() == 'none':
            new_org_id = None
        else:
            org_data = await get_org_by_name(org)
            if not org_data:
                await interaction.followup.send(embed=error_embed("Error", f"Organization `{org}` not found."))
                return
            new_org_id = org_data['id']

    await update_task(task_id, new_title, new_description, new_priority, new_org_id)

    changes = []
    if title       is not None: changes.append(f"Title → **{new_title}**")
    if description is not None: changes.append("Description updated")
    if priority    is not None: changes.append(f"Priority → **{PRIORITY_LABELS[new_priority]}**")
    if org         is not None: changes.append(f"Org → **{org if org.lower() != 'none' else 'None'}**")

    desc = "\n".join(changes) if changes else "No changes made."
    embed = success_embed(title=f"Task #{task_id} Updated", description=desc)
    embed.set_footer(text=f"#{task_id} • {new_title}")
    await interaction.followup.send(embed=embed)
