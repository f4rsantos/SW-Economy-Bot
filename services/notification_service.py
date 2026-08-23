# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import logging
from typing import Optional

import discord

from database.cache_manager import cache_manager
from repositories import notification_repo
from utils.embeds import create_embed

logger = logging.getLogger(__name__)

MODE_OFF = "off"
MODE_DM = "dm"
MODE_CHANNEL = "channel"
VALID_MODES = (MODE_OFF, MODE_DM, MODE_CHANNEL)

EVENT_TRANSFER = "transfer"
EVENT_MOVEMENT = "movement"

ROLE_ORIGIN = "origin"
ROLE_DESTINATION = "destination"

_bot = None


def set_bot(bot):
    global _bot
    _bot = bot


async def get_user_notification_settings(user_id: int) -> dict:
    user = cache_manager.get_user(user_id)
    if user is None:
        return {
            "mode": MODE_OFF,
            "channel_id": None,
            "transfers": True,
            "movements": True,
            "origin": True,
            "destination": True,
        }
    return {
        "mode": user.notify_mode,
        "channel_id": user.notify_channel_id,
        "transfers": user.notify_transfers,
        "movements": user.notify_movements,
        "origin": user.notify_origin,
        "destination": user.notify_destination,
    }


async def set_notification_mode(user_id: int, mode: str, channel_id: Optional[int] = None):
    if mode not in VALID_MODES:
        raise ValueError("Mode must be off, dm or channel.")
    if mode == MODE_CHANNEL and channel_id is None:
        raise ValueError("Pick a channel to receive notifications in.")
    if mode != MODE_CHANNEL:
        channel_id = None

    user_data = await notification_repo.set_user_notify_mode(user_id, mode, channel_id)
    if user_data is None:
        raise ValueError("You are not registered in the database yet.")
    cache_manager.users[user_id] = user_data
    return user_data


async def set_notification_events(
    user_id: int,
    transfers: bool,
    movements: bool,
    origin: bool,
    destination: bool,
):
    user_data = await notification_repo.set_user_notify_events(
        user_id, transfers, movements, origin, destination
    )
    if user_data is None:
        raise ValueError("You are not registered in the database yet.")
    cache_manager.users[user_id] = user_data
    return user_data


def _wants(settings: dict, event_type: str, role: str) -> bool:
    if settings["mode"] == MODE_OFF:
        return False
    if event_type == EVENT_TRANSFER and not settings["transfers"]:
        return False
    if event_type == EVENT_MOVEMENT and not settings["movements"]:
        return False
    if role == ROLE_ORIGIN and not settings["origin"]:
        return False
    if role == ROLE_DESTINATION and not settings["destination"]:
        return False
    return True


async def _collect_recipients(
    from_world_id: int,
    to_world_id: int,
    acting_faction_id: Optional[int],
    event_type: str,
) -> dict:
    recipients = {}

    for world_id, role in ((from_world_id, ROLE_ORIGIN), (to_world_id, ROLE_DESTINATION)):
        if world_id is None:
            continue
        rows = await notification_repo.get_interested_leader_rows(world_id, acting_faction_id)
        for row in rows:
            user_id = row["leader_id"]
            if user_id in recipients:
                continue
            settings = await get_user_notification_settings(user_id)
            if _wants(settings, event_type, role):
                recipients[user_id] = settings

    return recipients


async def _deliver(user_id: int, settings: dict, embed: discord.Embed):
    if _bot is None:
        return

    if settings["mode"] == MODE_DM:
        user = _bot.get_user(user_id)
        if user is None:
            user = await _bot.fetch_user(user_id)
        if user is None:
            return
        await user.send(embed=embed)
        return

    channel_id = settings["channel_id"]
    if channel_id is None:
        return
    channel = _bot.get_channel(channel_id)
    if channel is None:
        channel = await _bot.fetch_channel(channel_id)
    if channel is None:
        return
    await channel.send(content=f"<@{user_id}>", embed=embed)


async def _dispatch(recipients: dict, embed: discord.Embed):
    for user_id, settings in recipients.items():
        try:
            await _deliver(user_id, settings, embed)
        except Exception as e:
            logger.warning(f"Notification to user {user_id} failed: {e}")


async def notify_transfer_departure(
    from_faction_id: int,
    from_world_name: str,
    to_world_name: str,
    from_world_id: int,
    to_world_id: int,
    cargo_lines: list,
    escort_fleet_name: Optional[str] = None,
):
    recipients = await _collect_recipients(
        from_world_id, to_world_id, from_faction_id, EVENT_TRANSFER
    )
    if not recipients:
        return

    fields = [
        {"name": "From", "value": from_world_name, "inline": True},
        {"name": "To", "value": to_world_name, "inline": True},
    ]
    if cargo_lines:
        fields.append({"name": "Cargo", "value": "\n".join(cargo_lines), "inline": False})
    if escort_fleet_name:
        fields.append({"name": "Escort", "value": escort_fleet_name, "inline": True})

    embed = create_embed(
        title="Transfer Detected",
        description=f"A transfer has departed {from_world_name} bound for {to_world_name}.",
        fields=fields,
    )
    await _dispatch(recipients, embed)


async def notify_fleet_departure(
    faction_id: int,
    fleet_name: str,
    vehicle_count: int,
    from_world_name: str,
    to_world_name: str,
    from_world_id: int,
    to_world_id: int,
):
    recipients = await _collect_recipients(
        from_world_id, to_world_id, faction_id, EVENT_MOVEMENT
    )
    if not recipients:
        return

    fields = [
        {"name": "From", "value": from_world_name, "inline": True},
        {"name": "To", "value": to_world_name, "inline": True},
        {"name": "Unit", "value": fleet_name, "inline": True},
        {"name": "Vehicles", "value": str(vehicle_count), "inline": True},
    ]

    embed = create_embed(
        title="Unit Movement Detected",
        description=f"A unit has left {from_world_name} and is travelling to {to_world_name}.",
        fields=fields,
    )
    await _dispatch(recipients, embed)
