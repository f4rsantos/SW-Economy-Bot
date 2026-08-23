import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from services.user_service import get_user_ephemeral, set_user_ephemeral
from services.notification_service import (
    get_user_notification_settings,
    set_notification_mode,
    set_notification_events,
    MODE_OFF,
    MODE_DM,
    MODE_CHANNEL,
)

EPHEMERAL_HELP = (
    "When enabled, unit, vehicle, building, military and treasury commands reply "
    "only to you, but only for factions you lead. Everything else stays public."
)

NOTIFY_HELP = (
    "Get alerted when a transfer or a unit movement leaves or heads to a world where your "
    "faction holds land or keeps a unit with vehicles. Only faction leaders are notified, and "
    "your own faction activity never pings you."
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


@settings_group.command(name="notifications", description="Choose where movement alerts are sent")
@app_commands.describe(
    mode="Where to receive alerts",
    channel="Channel to post alerts in, required when mode is channel"
)
@app_commands.choices(mode=[
    app_commands.Choice(name="Off", value=MODE_OFF),
    app_commands.Choice(name="Direct message", value=MODE_DM),
    app_commands.Choice(name="Channel", value=MODE_CHANNEL),
])
@require_access_level(0)
async def settings_notifications(
    interaction: discord.Interaction,
    mode: app_commands.Choice[str],
    channel: discord.TextChannel = None
):
    await interaction.response.defer(ephemeral=True)

    try:
        await set_notification_mode(interaction.user.id, mode.value, channel.id if channel else None)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    if mode.value == MODE_CHANNEL:
        target = f"in {channel.mention}"
    elif mode.value == MODE_DM:
        target = "by direct message"
    else:
        target = "nowhere, alerts are off"

    embed = success_embed(
        title="Notifications Updated",
        description=f"Movement alerts will be sent {target}.\n\n{NOTIFY_HELP}"
    )
    await interaction.followup.send(embed=embed)


@settings_group.command(name="notification_events", description="Pick which movement alerts you receive")
@app_commands.describe(
    transfers="Alert on resource transfers",
    movements="Alert on unit movements",
    origin="Alert when something leaves one of your worlds",
    destination="Alert when something is heading to one of your worlds"
)
@require_access_level(0)
async def settings_notification_events(
    interaction: discord.Interaction,
    transfers: bool,
    movements: bool,
    origin: bool,
    destination: bool
):
    await interaction.response.defer(ephemeral=True)

    try:
        await set_notification_events(interaction.user.id, transfers, movements, origin, destination)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(title="Notification Events Updated", description=NOTIFY_HELP)
    embed.add_field(name="Transfers", value=f"`{'On' if transfers else 'Off'}`", inline=True)
    embed.add_field(name="Unit Movements", value=f"`{'On' if movements else 'Off'}`", inline=True)
    embed.add_field(name="Leaving Your Worlds", value=f"`{'On' if origin else 'Off'}`", inline=True)
    embed.add_field(name="Heading To Your Worlds", value=f"`{'On' if destination else 'Off'}`", inline=True)
    await interaction.followup.send(embed=embed)


@settings_group.command(name="view", description="View your personal bot settings")
@require_access_level(0)
async def settings_view(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    enabled = await get_user_ephemeral(interaction.user.id)
    state = "On" if enabled else "Off"

    notify = await get_user_notification_settings(interaction.user.id)
    if notify["mode"] == MODE_CHANNEL and notify["channel_id"]:
        notify_target = f"<#{notify['channel_id']}>"
    elif notify["mode"] == MODE_DM:
        notify_target = "Direct message"
    else:
        notify_target = "`Off`"

    embed = success_embed(title="Your Settings", description=EPHEMERAL_HELP)
    embed.add_field(name="Private Replies", value=f"`{state}`", inline=True)
    embed.add_field(name="Movement Alerts", value=notify_target, inline=True)
    if notify["mode"] != MODE_OFF:
        embed.add_field(name="Transfers", value=f"`{'On' if notify['transfers'] else 'Off'}`", inline=True)
        embed.add_field(name="Unit Movements", value=f"`{'On' if notify['movements'] else 'Off'}`", inline=True)
        embed.add_field(name="Leaving Your Worlds", value=f"`{'On' if notify['origin'] else 'Off'}`", inline=True)
        embed.add_field(name="Heading To Your Worlds", value=f"`{'On' if notify['destination'] else 'Off'}`", inline=True)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(settings_group)
