# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from utils.checks import require_access_level
from services.user_service import get_user_access_level
from services.utility_service import get_badge_names_for_user

_LEVEL_NAMES = {
    -10: "Banned", -1: "Declined ToS", 0: "Normal User",
    4: "DoE Gronk", 7: "Mapper", 9: "Administrator", 10: "System Administrator"
}


@app_commands.command(name="user", description="View user information")
@app_commands.describe(user="User to view info for (leave empty for yourself)")
@require_access_level(0)
async def user_info(interaction: discord.Interaction, user: discord.Member = None):
    await interaction.response.defer()

    target_user = user or interaction.user
    access_level = await get_user_access_level(target_user.id)
    badge_names_raw = await get_badge_names_for_user(target_user.id)

    embed = discord.Embed(
        title=f"User Info - {target_user.name}",
        color=target_user.color if target_user.color.value != 0 else 0x2ecc71
    )
    embed.set_thumbnail(url=target_user.display_avatar.url)
    embed.add_field(name="User ID", value=f"`{target_user.id}`", inline=True)
    embed.add_field(name="Access Level", value=f"`{access_level}` - {_LEVEL_NAMES.get(access_level, f'Level {access_level}')}", inline=True)

    badge_names = [f"**[{name}]**" for name in badge_names_raw]
    embed.add_field(
        name=f"Badges ({len(badge_names)})" if badge_names else "Badges",
        value=" ".join(badge_names) if badge_names else "No badges",
        inline=False
    )
    embed.add_field(name="Joined Server", value=f"<t:{int(target_user.joined_at.timestamp())}:R>" if target_user.joined_at else "Unknown", inline=True)
    embed.add_field(name="Account Created", value=f"<t:{int(target_user.created_at.timestamp())}:R>", inline=True)

    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(user_info)
