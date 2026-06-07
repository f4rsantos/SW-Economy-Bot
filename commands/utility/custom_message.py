import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from services.utility_service import (
    set_custom_message_for_user,
    delete_custom_message_for_user,
    get_custom_message_for_user,
)


@app_commands.command(name="set-custom-message", description="Set a custom message for a user (Level 9)")
@app_commands.describe(user="User to set message for", message="Custom message to show (leave empty to remove)")
@require_access_level(9)
async def set_custom_message(interaction: discord.Interaction, user: discord.User, message: Optional[str] = None):
    await interaction.response.defer()

    if message:
        if len(message) > 500:
            await interaction.followup.send(embed=error_embed("Error", "Message must be 500 characters or less."))
            return
        await set_custom_message_for_user(user.id, message, interaction.user.id)
        embed = success_embed("Custom Message Set", f"**User:** {user.mention}\n**Message:** {message}")
        embed.set_footer(text=f"Set by {interaction.user.name}")
    else:
        await delete_custom_message_for_user(user.id)
        embed = success_embed("Custom Message Removed", f"Removed custom message for {user.mention}")

    await interaction.followup.send(embed=embed)


@app_commands.command(name="view-custom-message", description="View a user's custom message")
@app_commands.describe(user="User to view message for (optional, defaults to yourself)")
@require_access_level(0)
async def view_custom_message(interaction: discord.Interaction, user: Optional[discord.User] = None):
    target_user = user or interaction.user
    message = await get_custom_message_for_user(target_user.id)

    if not message:
        await interaction.response.send_message(embed=error_embed("No Message", f"No custom message set for {target_user.mention}"))
        return

    embed = discord.Embed(title="Custom Message", description=message, color=0x00ff00)
    embed.set_author(name=target_user.name, icon_url=target_user.display_avatar.url)
    await interaction.response.send_message(embed=embed)


async def setup(bot):
    bot.tree.add_command(set_custom_message)
    bot.tree.add_command(view_custom_message)
