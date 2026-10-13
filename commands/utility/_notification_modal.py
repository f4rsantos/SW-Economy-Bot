# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import discord
from utils.embeds import success_embed, error_embed
from services.validation_service import require_world
from services.notification_service import (
    save_notification_settings,
    MODE_OFF,
    MODE_DM,
    MODE_CHANNEL,
    WORLD_MODE_ALL,
    WORLD_MODE_INCLUDE,
    WORLD_MODE_EXCLUDE,
)

ALERT_LABELS = (
    ("transfers", "Transfers"),
    ("movements", "Unit movements"),
    ("origin", "Leaving my worlds"),
    ("destination", "Heading to my worlds"),
    ("own", "My own transfers and movements"),
    ("recruitment", "Recruitment completed"),
    ("fleet_arrival", "Fleet arrival"),
    ("battle", "Battle ended"),
    ("income", "Income cycle"),
)

MODE_LABELS = (
    (MODE_OFF, "Off"),
    (MODE_DM, "Direct message"),
    (MODE_CHANNEL, "Channel"),
)

WORLD_MODE_LABELS = (
    (WORLD_MODE_ALL, "All worlds"),
    (WORLD_MODE_INCLUDE, "Only listed worlds"),
    (WORLD_MODE_EXCLUDE, "All except listed worlds"),
)

WORLD_FILTER_HELP = "World filter applies to transfers, unit movements, interceptions and fleet arrivals."


def _on_off(value: bool) -> str:
    return f"`{'On' if value else 'Off'}`"


class NotificationSettingsModal(discord.ui.Modal, title="Notification Settings"):
    def __init__(self, current: dict, world_names: list):
        super().__init__()

        self.mode_select = discord.ui.Select(
            options=[
                discord.SelectOption(label=label, value=value, default=value == current["mode"])
                for value, label in MODE_LABELS
            ],
        )
        self.add_item(discord.ui.Label(text="Delivery", component=self.mode_select))

        channel_defaults = [discord.Object(id=current["channel_id"])] if current["channel_id"] else []
        self.channel_select = discord.ui.ChannelSelect(
            channel_types=[discord.ChannelType.text],
            min_values=0,
            max_values=1,
            required=False,
            default_values=channel_defaults,
        )
        self.add_item(discord.ui.Label(
            text="Channel",
            description="Only used when delivery is Channel",
            component=self.channel_select,
        ))

        self.alerts_select = discord.ui.Select(
            min_values=0,
            max_values=len(ALERT_LABELS),
            required=False,
            options=[
                discord.SelectOption(label=label, value=flag, default=bool(current[flag]))
                for flag, label in ALERT_LABELS
            ],
        )
        self.add_item(discord.ui.Label(text="Alerts", component=self.alerts_select))

        self.world_mode_select = discord.ui.Select(
            options=[
                discord.SelectOption(label=label, value=value, default=value == current["world_mode"])
                for value, label in WORLD_MODE_LABELS
            ],
        )
        self.add_item(discord.ui.Label(text="World filter", component=self.world_mode_select))

        self.worlds_input = discord.ui.TextInput(
            style=discord.TextStyle.paragraph,
            required=False,
            max_length=1000,
            placeholder="Coruscant, Kuat, 42",
            default=", ".join(world_names) or None,
        )
        self.add_item(discord.ui.Label(
            text="Worlds",
            description="Names or IDs, separated by commas",
            component=self.worlds_input,
        ))

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()

        mode = self.mode_select.values[0]
        channel_id = self.channel_select.values[0].id if self.channel_select.values else None
        chosen = set(self.alerts_select.values)
        flags = {flag: flag in chosen for flag, _ in ALERT_LABELS}
        world_mode = self.world_mode_select.values[0]

        entries = [e.strip() for e in self.worlds_input.value.split(",") if e.strip()]
        results = await asyncio.gather(*(require_world(e) for e in entries))
        missing = [e for e, r in zip(entries, results) if not r.ok]
        if missing:
            await interaction.followup.send(embed=error_embed("Error", f"Worlds not found: {', '.join(missing)}."))
            return
        worlds = {r.data["id"]: r.data["name"] for r in results}

        try:
            await save_notification_settings(
                interaction.user.id, mode, channel_id, flags, world_mode, list(worlds.keys())
            )
        except ValueError as e:
            await interaction.followup.send(embed=error_embed("Error", str(e)))
            return

        if mode == MODE_CHANNEL:
            target = f"<#{channel_id}>"
        elif mode == MODE_DM:
            target = "Direct message"
        else:
            target = "`Off`"

        embed = success_embed(title="Notifications Updated", description=WORLD_FILTER_HELP)
        embed.add_field(name="Delivery", value=target, inline=True)
        for flag, label in ALERT_LABELS:
            embed.add_field(name=label, value=_on_off(flags[flag]), inline=True)
        world_mode_label = dict(WORLD_MODE_LABELS)[world_mode]
        if world_mode != WORLD_MODE_ALL:
            world_mode_label += f": {', '.join(worlds.values())}"
        embed.add_field(name="World Filter", value=world_mode_label[:1024], inline=False)
        await interaction.followup.send(embed=embed)
