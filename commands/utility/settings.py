import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from services.user_service import get_user_ephemeral, set_user_ephemeral

EPHEMERAL_HELP = (
    "When enabled, unit, vehicle, building, military and treasury commands reply "
    "only to you, but only for factions you lead. Everything else stays public."
)

settings_group = app_commands.Group(name="settings", description="Manage your personal bot settings")


@settings_group.command(name="ephemeral", description="Make your faction commands reply only to you")
@app_commands.describe(enabled="Turn private replies on or off")
@require_access_level(0)
async def settings_ephemeral(interaction: discord.Interaction, enabled: bool):
    await interaction.response.defer(ephemeral=True)

    try:
        await set_user_ephemeral(interaction.user.id, enabled)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    state = "enabled" if enabled else "disabled"
    embed = success_embed(
        title=f"Private Replies {state.capitalize()}",
        description=f"Private replies are now **{state}**.\n\n{EPHEMERAL_HELP}"
    )
    await interaction.followup.send(embed=embed)


@settings_group.command(name="view", description="View your personal bot settings")
@require_access_level(0)
async def settings_view(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    enabled = await get_user_ephemeral(interaction.user.id)
    state = "On" if enabled else "Off"

    embed = success_embed(title="Your Settings", description=EPHEMERAL_HELP)
    embed.add_field(name="Private Replies", value=f"`{state}`", inline=True)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(settings_group)
