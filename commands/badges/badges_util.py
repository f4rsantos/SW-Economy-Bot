# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from services.user_service import check_user_exists
from services.utility_service import (
    badge_name_exists,
    create_badge,
    get_user_access_row,
    add_badge_to_user,
    remove_badge_from_user,
    get_all_badges,
)
from services.validation_service import require_badge


@app_commands.command(name="new", description="Create a new badge (Level 9)")
@app_commands.describe(name="Badge name (will be displayed as **[name]**)")
@require_access_level(9)
async def new_badge(interaction: discord.Interaction, name: str):
    await interaction.response.defer()

    if not (1 <= len(name) <= 50):
        await interaction.followup.send(embed=error_embed("Error", "Badge name must be 1-50 characters."))
        return

    if await badge_name_exists(name):
        await interaction.followup.send(embed=error_embed("Error", f"A badge named '**{name}**' already exists."))
        return

    badge_id = await create_badge(name)
    await interaction.followup.send(embed=success_embed("Badge Created", f"**[{name}]** (ID: {badge_id})"))


@app_commands.command(name="add", description="Award a badge to a user (Level 9)")
@app_commands.describe(user="User to award the badge to", badge="Badge name or ID to award")
@require_access_level(9)
async def add_badge(interaction: discord.Interaction, user: discord.Member, badge: str):
    await interaction.response.defer()

    r_badge = await require_badge(badge)
    if not r_badge.ok:
        await interaction.followup.send(embed=error_embed("Error", r_badge.error))
        return

    if not await check_user_exists(user.id):
        await interaction.followup.send(embed=error_embed("Error", f"{user.mention} does not exist in the database."))
        return

    user_data = await get_user_access_row(user.id)
    current_badges = list(user_data.badge_ids) if user_data else []
    if r_badge.data['id'] in current_badges:
        await interaction.followup.send(embed=error_embed("Error", f"{user.mention} already has the **[{r_badge.data['name']}]** badge."))
        return

    await add_badge_to_user(user.id, r_badge.data['id'])
    await interaction.followup.send(embed=success_embed("Badge Awarded", f"{user.mention} has been awarded **[{r_badge.data['name']}]**"))


@app_commands.command(name="remove", description="Remove a badge from a user (Level 9)")
@app_commands.describe(user="User to remove the badge from", badge="Badge name or ID to remove")
@require_access_level(9)
async def remove_badge(interaction: discord.Interaction, user: discord.Member, badge: str):
    await interaction.response.defer()

    r_badge = await require_badge(badge)
    if not r_badge.ok:
        await interaction.followup.send(embed=error_embed("Error", r_badge.error))
        return

    user_data = await get_user_access_row(user.id)
    if not user_data or not user_data.badge_ids or r_badge.data['id'] not in user_data.badge_ids:
        await interaction.followup.send(embed=error_embed("Error", f"{user.mention} does not have the **[{r_badge.data['name']}]** badge."))
        return

    await remove_badge_from_user(user.id, r_badge.data['id'])
    await interaction.followup.send(embed=success_embed("Badge Removed", f"**[{r_badge.data['name']}]** has been removed from {user.mention}"))


@app_commands.command(name="list", description="List all available badges")
@require_access_level(0)
async def list_badges(interaction: discord.Interaction):
    await interaction.response.defer()

    badges = await get_all_badges()
    if not badges:
        await interaction.followup.send(embed=error_embed("No Badges", "No badges have been created yet."))
        return

    embed = discord.Embed(title="Available Badges", description=f"Total: {len(badges)} badge(s)", color=0x00ff00)
    embed.add_field(name="Badges", value="\n".join(f"**[{b['name']}]** (ID: {b['id']})" for b in badges), inline=False)
    await interaction.followup.send(embed=embed)
