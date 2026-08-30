from typing import Optional
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from services.user_service import (
    get_user_ephemeral,
    set_user_ephemeral,
    get_user_allegiance,
    get_user_treatment,
    clear_user_allegiance,
    request_user_allegiance,
    set_user_treatment,
)
from services.validation_service import require_faction
from services.notification_service import (
    get_user_notification_settings,
    set_notification_mode,
    set_notification_events,
    set_notification_activity,
    MODE_OFF,
    MODE_DM,
    MODE_CHANNEL,
)

ALLEGIANCE_HELP = (
    "Your allegiance is the faction you serve, shown on your user info card. "
    "Declaring an allegiance sends a request that the faction's leader must approve "
    "before it takes effect. Clearing your allegiance takes effect immediately."
)

TREATMENT_HELP = (
    "Your treatment is the title or style others use to address you, shown on your user info card. "
    "You do not need to be a faction leader to set your own treatment."
)

EPHEMERAL_HELP = (
    "When enabled, unit, vehicle, building, military and treasury commands reply "
    "only to you, but only for factions you lead. Everything else stays public."
)

VIEW_HELP = (
    "Your personal bot settings. These replies are public, so anyone in the channel "
    "can see them. Private Replies below controls your faction command replies, not this one."
)

NOTIFY_HELP = (
    "Get alerted when a transfer or a unit movement leaves or heads to a world where your "
    "faction holds land or keeps a unit with vehicles. Alerts reach the faction's leader and "
    "any member whose allegiance is approved for that faction, as long as they opt in below. "
    "Turn on Own Activity to also be alerted about your own faction's transfers and movements."
)

ACTIVITY_HELP = (
    "Get alerted about your own faction's recruitment, fleet arrivals, battles "
    "and income cycles. Alerts reach the faction's leader and any member whose allegiance is "
    "approved for that faction, as long as they opt in below, and these alerts never cover "
    "other factions' activity."
)

settings_group = app_commands.Group(name="settings", description="Manage your personal bot settings")


@settings_group.command(name="ephemeral", description="Make your faction commands reply only to you")
@app_commands.describe(enabled="Turn private replies on or off")
@require_access_level(0)
async def settings_ephemeral(interaction: discord.Interaction, enabled: bool):
    await interaction.response.defer()

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
    await interaction.response.defer()

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
    destination="Alert when something is heading to one of your worlds",
    own_activity="Also alert on your own faction's transfers and movements"
)
@require_access_level(0)
async def settings_notification_events(
    interaction: discord.Interaction,
    transfers: bool,
    movements: bool,
    origin: bool,
    destination: bool,
    own_activity: bool
):
    await interaction.response.defer()

    try:
        await set_notification_events(interaction.user.id, transfers, movements, origin, destination, own_activity)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(title="Notification Events Updated", description=NOTIFY_HELP)
    embed.add_field(name="Transfers", value=f"`{'On' if transfers else 'Off'}`", inline=True)
    embed.add_field(name="Unit Movements", value=f"`{'On' if movements else 'Off'}`", inline=True)
    embed.add_field(name="Leaving Your Worlds", value=f"`{'On' if origin else 'Off'}`", inline=True)
    embed.add_field(name="Heading To Your Worlds", value=f"`{'On' if destination else 'Off'}`", inline=True)
    embed.add_field(name="Own Activity", value=f"`{'On' if own_activity else 'Off'}`", inline=True)
    await interaction.followup.send(embed=embed)


@settings_group.command(name="activity_events", description="Pick which own faction activity alerts you receive")
@app_commands.describe(
    recruitment="Alert when your recruitment orders finish",
    fleet_arrival="Alert when your units arrive at a destination",
    battle="Alert when a battle your faction is in ends",
    income="Alert when the weekly income cycle completes"
)
@require_access_level(0)
async def settings_activity_events(
    interaction: discord.Interaction,
    recruitment: bool,
    fleet_arrival: bool,
    battle: bool,
    income: bool
):
    await interaction.response.defer()

    try:
        await set_notification_activity(
            interaction.user.id, recruitment, fleet_arrival, battle, income
        )
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(title="Activity Alerts Updated", description=ACTIVITY_HELP)
    embed.add_field(name="Recruitment", value=f"`{'On' if recruitment else 'Off'}`", inline=True)
    embed.add_field(name="Fleet Arrival", value=f"`{'On' if fleet_arrival else 'Off'}`", inline=True)
    embed.add_field(name="Battle", value=f"`{'On' if battle else 'Off'}`", inline=True)
    embed.add_field(name="Income Cycle", value=f"`{'On' if income else 'Off'}`", inline=True)
    await interaction.followup.send(embed=embed)


@settings_group.command(name="allegiance", description="Request the faction you serve on your user info card")
@app_commands.describe(faction="The faction you serve (leave empty to clear)")
@require_access_level(0)
async def settings_allegiance(interaction: discord.Interaction, faction: Optional[str] = None):
    await interaction.response.defer()

    if not faction:
        try:
            await clear_user_allegiance(interaction.user.id)
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", str(e)))
            return

        description = f"Your allegiance has been cleared.\n\n{ALLEGIANCE_HELP}"
        embed = success_embed(title="Allegiance Cleared", description=description)
        await interaction.followup.send(embed=embed)
        return

    r_faction = await require_faction(faction)
    if not r_faction.ok:
        await interaction.followup.send(embed=error_embed("Error", r_faction.error))
        return
    faction_data = r_faction.data

    try:
        await request_user_allegiance(interaction.user.id, faction_data.id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    description = (
        f"Your request to declare allegiance to **{faction_data.display_name}** has been sent "
        f"and awaits approval from that faction's leader.\n\n{ALLEGIANCE_HELP}"
    )
    embed = success_embed(title="Allegiance Requested", description=description)
    await interaction.followup.send(embed=embed)


@settings_group.command(name="treatment", description="Set your own title or how you want to be addressed")
@app_commands.describe(treatment="Your title or preferred form of address (leave empty to clear)")
@require_access_level(0)
async def settings_treatment(interaction: discord.Interaction, treatment: Optional[str] = None):
    await interaction.response.defer()

    try:
        await set_user_treatment(interaction.user.id, treatment)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    description = f"Your treatment is now **{treatment}**.\n\n{TREATMENT_HELP}" if treatment else f"Your treatment has been cleared.\n\n{TREATMENT_HELP}"
    embed = success_embed(title="Treatment Updated", description=description)
    await interaction.followup.send(embed=embed)


@settings_group.command(name="view", description="View your personal bot settings")
@require_access_level(0)
async def settings_view(interaction: discord.Interaction):
    await interaction.response.defer()

    enabled = await get_user_ephemeral(interaction.user.id)
    state = "On" if enabled else "Off"

    allegiance = await get_user_allegiance(interaction.user.id)
    treatment = await get_user_treatment(interaction.user.id)

    notify = await get_user_notification_settings(interaction.user.id)
    if notify["mode"] == MODE_CHANNEL and notify["channel_id"]:
        notify_target = f"<#{notify['channel_id']}>"
    elif notify["mode"] == MODE_DM:
        notify_target = "Direct message"
    else:
        notify_target = "`Off`"

    embed = success_embed(title="Your Settings", description=VIEW_HELP)
    embed.add_field(name="Private Replies", value=f"`{state}`", inline=True)
    embed.add_field(name="Allegiance", value=allegiance or "`None`", inline=True)
    embed.add_field(name="Treatment", value=treatment or "`None`", inline=True)
    embed.add_field(name="Movement Alerts", value=notify_target, inline=True)
    if notify["mode"] != MODE_OFF:
        embed.add_field(name="Transfers", value=f"`{'On' if notify['transfers'] else 'Off'}`", inline=True)
        embed.add_field(name="Unit Movements", value=f"`{'On' if notify['movements'] else 'Off'}`", inline=True)
        embed.add_field(name="Leaving Your Worlds", value=f"`{'On' if notify['origin'] else 'Off'}`", inline=True)
        embed.add_field(name="Heading To Your Worlds", value=f"`{'On' if notify['destination'] else 'Off'}`", inline=True)
        embed.add_field(name="Own Activity", value=f"`{'On' if notify['own'] else 'Off'}`", inline=True)
        embed.add_field(name="Recruitment Alerts", value=f"`{'On' if notify['recruitment'] else 'Off'}`", inline=True)
        embed.add_field(name="Fleet Arrival Alerts", value=f"`{'On' if notify['fleet_arrival'] else 'Off'}`", inline=True)
        embed.add_field(name="Battle Alerts", value=f"`{'On' if notify['battle'] else 'Off'}`", inline=True)
        embed.add_field(name="Income Cycle Alerts", value=f"`{'On' if notify['income'] else 'Off'}`", inline=True)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(settings_group)
