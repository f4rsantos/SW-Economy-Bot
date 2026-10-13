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
    MODE_OFF,
    MODE_DM,
    MODE_CHANNEL,
    WORLD_MODE_ALL,
)
from database.static_cache import static_cache
from commands.utility._notification_modal import NotificationSettingsModal, WORLD_MODE_LABELS

ALLEGIANCE_HELP = "Declaring an allegiance sends a request that the faction's leader must approve. Clearing it is immediate."

TREATMENT_HELP = "Your treatment is the title others use to address you, shown on your user info card."

EPHEMERAL_HELP = "Unit, vehicle, building, military and treasury commands reply only to you, for factions you lead."

VIEW_HELP = "Your personal bot settings. This reply is public."



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


def _world_names(world_ids) -> list:
    names = []
    for world_id in world_ids:
        world = static_cache.get_world_by_id(world_id)
        names.append(world["name"] if world else str(world_id))
    return names


@settings_group.command(name="notifications", description="Configure where alerts go, which alerts you get and for which worlds")
@require_access_level(0)
async def settings_notifications(interaction: discord.Interaction):
    current = await get_user_notification_settings(interaction.user.id)
    modal = NotificationSettingsModal(current, _world_names(current["world_ids"]))
    await interaction.response.send_modal(modal)


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
        world_filter = dict(WORLD_MODE_LABELS)[notify["world_mode"]]
        if notify["world_mode"] != WORLD_MODE_ALL:
            world_filter += f": {', '.join(_world_names(notify['world_ids']))}"
        embed.add_field(name="World Filter", value=world_filter[:1024], inline=False)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(settings_group)
