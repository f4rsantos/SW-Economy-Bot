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
EVENT_RECRUITMENT = "recruitment"
EVENT_FLEET_ARRIVAL = "fleet_arrival"
EVENT_BATTLE = "battle"
EVENT_INCOME = "income"
EVENT_INTERCEPTION = "interception"

OWN_ONLY_EVENTS = (
    EVENT_INTERCEPTION,
    EVENT_RECRUITMENT,
    EVENT_FLEET_ARRIVAL,
    EVENT_BATTLE,
    EVENT_INCOME,
)

WORLD_MODE_ALL = "all"
WORLD_MODE_INCLUDE = "include"
WORLD_MODE_EXCLUDE = "exclude"
VALID_WORLD_MODES = (WORLD_MODE_ALL, WORLD_MODE_INCLUDE, WORLD_MODE_EXCLUDE)

ALERT_FLAGS = (
    "transfers",
    "movements",
    "origin",
    "destination",
    "own",
    "recruitment",
    "fleet_arrival",
    "battle",
    "income",
)

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
            "own": False,
            "recruitment": True,
            "fleet_arrival": True,
            "battle": True,
            "income": True,
            "world_mode": WORLD_MODE_ALL,
            "world_ids": (),
        }
    return {
        "mode": user.notify_mode,
        "channel_id": user.notify_channel_id,
        "transfers": user.notify_transfers,
        "movements": user.notify_movements,
        "origin": user.notify_origin,
        "destination": user.notify_destination,
        "own": user.notify_own,
        "recruitment": user.notify_recruitment,
        "fleet_arrival": user.notify_fleet_arrival,
        "battle": user.notify_battle,
        "income": user.notify_income,
        "world_mode": user.notify_world_mode,
        "world_ids": user.notify_world_ids,
    }


async def save_notification_settings(
    user_id: int,
    mode: str,
    channel_id: Optional[int],
    flags: dict,
    world_mode: str,
    world_ids: list,
):
    if mode not in VALID_MODES:
        raise ValueError("Mode must be off, dm or channel.")
    if mode == MODE_CHANNEL and channel_id is None:
        raise ValueError("Pick a channel to receive notifications in.")
    if mode != MODE_CHANNEL:
        channel_id = None
    if world_mode not in VALID_WORLD_MODES:
        raise ValueError("World filter must be all, include or exclude.")
    if world_mode != WORLD_MODE_ALL and not world_ids:
        raise ValueError("List at least one world for this world filter.")
    if world_mode == WORLD_MODE_ALL:
        world_ids = []

    clean_flags = {flag: bool(flags.get(flag, False)) for flag in ALERT_FLAGS}
    user_data = await notification_repo.set_user_notify_settings(
        user_id, mode, channel_id, clean_flags, world_mode, sorted(set(world_ids))
    )
    if user_data is None:
        raise ValueError("You are not registered in the database yet.")
    cache_manager.users[user_id] = user_data
    return user_data


def _world_allowed(settings: dict, world_id: Optional[int]) -> bool:
    mode = settings.get("world_mode", WORLD_MODE_ALL)
    if mode == WORLD_MODE_ALL or world_id is None:
        return True
    listed = world_id in settings.get("world_ids", ())
    return listed if mode == WORLD_MODE_INCLUDE else not listed


def _wants(settings: dict, event_type: str, role: Optional[str], is_own: bool) -> bool:
    if settings["mode"] == MODE_OFF:
        return False

    if event_type in OWN_ONLY_EVENTS:
        if not is_own:
            return False
        if event_type == EVENT_INTERCEPTION and not settings["transfers"]:
            return False
        if event_type == EVENT_RECRUITMENT and not settings["recruitment"]:
            return False
        if event_type == EVENT_FLEET_ARRIVAL and not settings["fleet_arrival"]:
            return False
        if event_type == EVENT_BATTLE and not settings["battle"]:
            return False
        if event_type == EVENT_INCOME and not settings["income"]:
            return False
        return True

    if is_own and not settings["own"]:
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
            user_id = row["user_id"]
            is_own = bool(row["is_own"])
            if user_id not in recipients:
                settings = await get_user_notification_settings(user_id)
                if _wants(settings, event_type, role, is_own) and _world_allowed(settings, world_id):
                    recipients[user_id] = (settings, is_own)

            if is_own or not row["is_leader"]:
                continue

            partner_rows = await notification_repo.get_foreign_sharing_partner_leader_ids(
                row["faction_id"], user_id
            )
            for partner_row in partner_rows:
                partner_user_id = partner_row["leader_id"]
                if partner_user_id in recipients:
                    continue
                partner_settings = await get_user_notification_settings(partner_user_id)
                if _wants(partner_settings, event_type, role, False) and _world_allowed(partner_settings, world_id):
                    recipients[partner_user_id] = (partner_settings, False)

    return recipients


async def _collect_faction_recipients(
    faction_id: Optional[int],
    event_type: str,
    world_id: Optional[int] = None,
) -> dict:
    if faction_id is None:
        return {}
    rows = await notification_repo.get_faction_recipient_rows(faction_id)
    recipients = {}
    for row in rows:
        user_id = row["user_id"]
        if user_id in recipients:
            continue
        settings = await get_user_notification_settings(user_id)
        if _wants(settings, event_type, None, True) and _world_allowed(settings, world_id):
            recipients[user_id] = (settings, True)
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
    for user_id, (settings, _is_own) in recipients.items():
        try:
            await _deliver(user_id, settings, embed)
        except Exception as e:
            logger.warning(f"Notification to user {user_id} failed: {e}")


async def _dispatch_variant(recipients: dict, build_embed):
    for user_id, (settings, is_own) in recipients.items():
        try:
            embed = build_embed(is_own)
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
    transfer_id: Optional[int] = None,
):
    recipients = await _collect_recipients(
        from_world_id, to_world_id, from_faction_id, EVENT_TRANSFER
    )
    if not recipients:
        return

    owner = cache_manager.get_faction(from_faction_id)
    owner_name = owner.display_name if owner else "Unknown faction"

    fields = [
        {"name": "Faction", "value": owner_name, "inline": True},
        {"name": "From", "value": from_world_name, "inline": True},
        {"name": "To", "value": to_world_name, "inline": True},
    ]
    if transfer_id is not None:
        fields.append({"name": "ID", "value": str(transfer_id), "inline": True})
    if cargo_lines:
        fields.append({"name": "Cargo", "value": "\n".join(cargo_lines), "inline": False})
    if escort_fleet_name:
        fields.append({"name": "Escort", "value": escort_fleet_name, "inline": True})

    def build_embed(is_own: bool) -> discord.Embed:
        description = (
            f"Your faction's transfer has departed {from_world_name} bound for {to_world_name}."
            if is_own
            else f"A transfer from {owner_name} has departed {from_world_name} bound for {to_world_name}."
        )
        return create_embed(title="Transfer Detected", description=description, fields=fields)

    await _dispatch_variant(recipients, build_embed)


async def notify_fleet_departure(
    faction_id: int,
    fleet_name: str,
    vehicle_count: int,
    from_world_name: str,
    to_world_name: str,
    from_world_id: int,
    to_world_id: int,
    is_stealth: bool = False,
):
    recipients = await _collect_recipients(
        from_world_id, to_world_id, faction_id, EVENT_MOVEMENT
    )
    if not recipients:
        return

    owner = cache_manager.get_faction(faction_id)
    owner_name = owner.display_name if owner else "Unknown faction"

    own_fields = [
        {"name": "Faction", "value": owner_name, "inline": True},
        {"name": "From", "value": from_world_name, "inline": True},
        {"name": "To", "value": to_world_name, "inline": True},
        {"name": "Unit", "value": fleet_name, "inline": True},
        {"name": "Vehicles", "value": str(vehicle_count), "inline": True},
    ]
    contact_fields = [
        {"name": "From", "value": from_world_name, "inline": True},
        {"name": "To", "value": to_world_name, "inline": True},
        {"name": "Ships", "value": str(vehicle_count), "inline": True},
    ]

    def build_embed(is_own: bool) -> discord.Embed:
        if is_own:
            description = f"Your unit has left {from_world_name} and is travelling to {to_world_name}."
            return create_embed(title="Unit Movement Detected", description=description, fields=own_fields)
        if is_stealth:
            description = (
                f"An unidentified contact has left {from_world_name} and is travelling to {to_world_name}."
            )
            return create_embed(title="Unit Movement Detected", description=description, fields=contact_fields)
        description = f"A unit from {owner_name} has left {from_world_name} and is travelling to {to_world_name}."
        return create_embed(title="Unit Movement Detected", description=description, fields=own_fields)

    await _dispatch_variant(recipients, build_embed)


async def notify_recruitment_complete(
    faction_id: int,
    fleet_name: str,
    amount: int,
):
    recipients = await _collect_faction_recipients(faction_id, EVENT_RECRUITMENT)
    if not recipients:
        return

    fields = [
        {"name": "Unit", "value": fleet_name, "inline": True},
        {"name": "Soldiers", "value": str(amount), "inline": True},
    ]
    embed = create_embed(
        title="Recruitment Completed",
        description="Your recruitment order has finished training.",
        fields=fields,
    )
    await _dispatch(recipients, embed)


async def notify_fleet_arrival(
    faction_id: int,
    fleet_name: str,
    world_name: str,
    world_id: Optional[int] = None,
):
    recipients = await _collect_faction_recipients(faction_id, EVENT_FLEET_ARRIVAL, world_id)
    if not recipients:
        return

    fields = [
        {"name": "Unit", "value": fleet_name, "inline": True},
        {"name": "World", "value": world_name, "inline": True},
    ]
    embed = create_embed(
        title="Fleet Arrival",
        description=f"Your unit has arrived at {world_name}.",
        fields=fields,
    )
    await _dispatch(recipients, embed)


async def notify_battle_ended(
    battle_id: int,
    world_name: str,
    participant_faction_ids: list,
):
    recipients = {}
    for faction_id in participant_faction_ids:
        recipients.update(await _collect_faction_recipients(faction_id, EVENT_BATTLE))
    if not recipients:
        return

    embed = create_embed(
        title="Battle Ended",
        description=f"Battle #{battle_id} at {world_name} has ended.",
    )
    await _dispatch(recipients, embed)


async def notify_allegiance_resolved(user_id: int, faction_display_name: str, approved: bool):
    if _bot is None:
        return

    if approved:
        description = f"Your request to declare allegiance to **{faction_display_name}** has been approved."
        title = "Allegiance Approved"
    else:
        description = f"Your request to declare allegiance to **{faction_display_name}** has been denied."
        title = "Allegiance Denied"

    embed = create_embed(title=title, description=description)

    user = _bot.get_user(user_id)
    if user is None:
        user = await _bot.fetch_user(user_id)
    if user is None:
        return
    await user.send(embed=embed)


async def notify_income_cycle_complete():
    factions = cache_manager.get_all_factions()
    recipients = {}
    for faction_id in factions:
        recipients.update(await _collect_faction_recipients(faction_id, EVENT_INCOME))
    if not recipients:
        return

    embed = create_embed(
        title="Income Cycle Completed",
        description="Your faction's weekly income cycle has been processed.",
    )
    await _dispatch(recipients, embed)


async def notify_transfer_intercepted(
    owner_faction_id: int,
    transfer_id: int,
    from_world_name: str,
    to_world_name: str,
    interception_world_name: Optional[str] = None,
    intercepting_faction_name: Optional[str] = None,
    interception_world_id: Optional[int] = None,
):
    recipients = await _collect_faction_recipients(owner_faction_id, EVENT_INTERCEPTION, interception_world_id)
    if not recipients:
        return

    fields = [
        {"name": "ID", "value": str(transfer_id), "inline": True},
        {"name": "From", "value": from_world_name, "inline": True},
        {"name": "To", "value": to_world_name, "inline": True},
    ]
    if interception_world_name:
        fields.append({"name": "Held at", "value": interception_world_name, "inline": True})
    if intercepting_faction_name:
        fields.append({"name": "Intercepted by", "value": intercepting_faction_name, "inline": True})

    where = f" at {interception_world_name}" if interception_world_name else ""
    embed = create_embed(
        title="Transfer Intercepted",
        description=f"Your transfer bound for {to_world_name} was intercepted{where}.",
        fields=fields,
    )
    await _dispatch(recipients, embed)
