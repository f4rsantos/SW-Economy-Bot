import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from services.user_service import get_user_access_level, update_user_access_level, create_user, check_user_exists

_LEVEL_NAMES = {
    -10: "Banned (Cannot use commands)",
    -1: "Denied (Cannot use commands)",
    0: "Normal User",
    4: "DoE Gronk",
    7: "Mapper",
    9: "Administrator",
    10: "System Administrator"
}


@app_commands.command(name="accesslevel", description="Set a user's access level (Admin only)")
@app_commands.describe(user="The user whose access level you want to change", level="The access level to assign (-10 to 9)")
@require_access_level(9)
async def access_level(interaction: discord.Interaction, user: discord.Member, level: app_commands.Range[int, -10, 9]):
    await interaction.response.defer()

    command_user_level = await get_user_access_level(interaction.user.id)
    target_current_level = await get_user_access_level(user.id)

    if command_user_level == 9 and target_current_level >= 9:
        await interaction.followup.send(embed=error_embed("Access Denied", f"You cannot modify users with access level 9 or higher.\nTarget user's level: **{target_current_level}**"))
        return

    max_assignable = command_user_level - 1
    if level > max_assignable:
        await interaction.followup.send(embed=error_embed("Access Denied", f"You can only assign access levels up to **{max_assignable}**.\nYour access level: **{command_user_level}**"))
        return

    if user.id == interaction.user.id:
        await interaction.followup.send(embed=error_embed("Error", "You cannot modify your own access level."))
        return

    if await check_user_exists(user.id):
        await update_user_access_level(user.id, level)
    else:
        await create_user(user.id, access_level=level)

    level_text = _LEVEL_NAMES.get(level, f"Level {level}")
    embed = success_embed("Access Level Updated", f"{user.mention} has been assigned access level **{level}**")
    embed.add_field(name="User", value=f"{user.name} ({user.id})", inline=True)
    embed.add_field(name="New Level", value=level_text, inline=True)
    embed.add_field(name="Set By", value=interaction.user.mention, inline=True)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(access_level)
