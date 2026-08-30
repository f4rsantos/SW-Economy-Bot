# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import io

import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.badge_art import render_user_card_png
from services.user_service import get_user_access_level, get_user_allegiance, get_user_treatment
from services.badge_service import get_user_badge_ids, get_badges_info

_LEVEL_NAMES = {
    -10: "Banned", -1: "Declined ToS", 0: "Normal User",
    4: "DoE Gronk", 7: "Mapper", 9: "Administrator", 10: "System Administrator"
}


async def _fetch_avatar_bytes(target_user: discord.abc.User) -> bytes | None:
    try:
        avatar_asset = target_user.display_avatar.replace(format="png", size=256)
        return await avatar_asset.read()
    except Exception:
        return None


@app_commands.command(name="user", description="View user information")
@app_commands.describe(user="User to view info for (leave empty for yourself)")
@require_access_level(0)
async def user_info(interaction: discord.Interaction, user: discord.Member = None):
    await interaction.response.defer()

    target_user = user or interaction.user
    access_level = await get_user_access_level(target_user.id)
    allegiance = await get_user_allegiance(target_user.id)
    treatment = await get_user_treatment(target_user.id)
    badge_ids = await get_user_badge_ids(target_user.id)
    badges = await get_badges_info(badge_ids)
    avatar_bytes = await _fetch_avatar_bytes(target_user)

    embed = discord.Embed(
        title=f"User Info - {target_user.name}",
        color=target_user.color if target_user.color.value != 0 else 0x2ecc71
    )
    embed.add_field(name="User ID", value=f"`{target_user.id}`", inline=True)
    embed.add_field(name="Access Level", value=f"`{access_level}` - {_LEVEL_NAMES.get(access_level, f'Level {access_level}')}", inline=True)
    embed.add_field(name="Allegiance", value=allegiance or "None", inline=True)
    embed.add_field(name="Treatment", value=treatment or "None", inline=True)
    embed.add_field(name="Badges", value=str(len(badges)), inline=True)
    embed.add_field(name="Joined Server", value=f"<t:{int(target_user.joined_at.timestamp())}:R>" if target_user.joined_at else "Unknown", inline=True)
    embed.add_field(name="Account Created", value=f"<t:{int(target_user.created_at.timestamp())}:R>", inline=True)

    card_bytes = render_user_card_png(
        avatar_bytes,
        target_user.name,
        treatment,
        [(badge.id, badge.name) for badge in badges],
    )
    file = discord.File(fp=io.BytesIO(card_bytes), filename="user_card.png")
    embed.set_image(url="attachment://user_card.png")

    await interaction.followup.send(embed=embed, file=file)


async def setup(bot):
    bot.tree.add_command(user_info)
