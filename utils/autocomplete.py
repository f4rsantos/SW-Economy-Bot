# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from services.faction_service import search_faction_names
from services.map_service import search_world_names
from services.building_service import search_building_names


async def faction_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    names = await search_faction_names(current, 25)
    return [app_commands.Choice(name=name, value=name) for name in names]


async def world_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    names = await search_world_names(current, 25)
    return [app_commands.Choice(name=name, value=name) for name in names]


async def building_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    buildings = await search_building_names(current, 25)
    return [app_commands.Choice(name=f"{b.name} (ID: {b.id})", value=str(b.id)) for b in buildings]


async def pact_type_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    from services.pact_service import get_pact_type_names

    names = await get_pact_type_names()
    current_lower = current.lower()
    choices = []
    for name in names:
        if current_lower and current_lower not in name.lower():
            continue
        choices.append(app_commands.Choice(name=name, value=name))
        if len(choices) >= 25:
            break
    return choices


async def port_world_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    from services import port_service
    from services.validation_service import require_faction

    faction_name = getattr(interaction.namespace, 'faction', None)
    if not faction_name:
        return []

    r_faction = await require_faction(faction_name)
    if not r_faction.ok:
        return []

    ports = await port_service.list_faction_ports(r_faction.data.id)
    current_lower = current.lower()
    choices = []
    for port in ports:
        if current_lower and current_lower not in port.world_name.lower():
            continue
        choices.append(app_commands.Choice(name=port.world_name, value=port.world_name))
        if len(choices) >= 25:
            break
    return choices


async def vehicle_type_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    from database.static_cache import static_cache

    current_lower = current.lower()
    choices = []
    for name in static_cache.vehicle_types_by_id.values():
        if current_lower and current_lower not in name.lower():
            continue
        choices.append(app_commands.Choice(name=name, value=name))
        if len(choices) >= 25:
            break
    return choices


async def debris_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    from services.fleet_service import list_debris_fleets
    from services.validation_service import require_faction

    faction_name = getattr(interaction.namespace, 'faction', None)
    faction_id = None
    if faction_name:
        r_faction = await require_faction(faction_name)
        if r_faction.ok:
            faction_id = r_faction.data.id

    rows = await list_debris_fleets(faction_id=faction_id)

    from services.intelligence_service import get_user_faction_id, get_observed_worlds
    viewer_faction_id = await get_user_faction_id(interaction.user.id)
    if viewer_faction_id is None:
        return []
    observed = await get_observed_worlds(viewer_faction_id)
    rows = [r for r in rows if r['faction_id'] == viewer_faction_id or r['world_id'] in observed]

    current_lower = current.lower()
    choices = []
    for r in rows:
        fname = r['name'] or f"Fleet #{r['faction_fleet_number']}"
        label = f"{r['faction_name']} - {fname} at {r['world_name']} ({r['total_cs']:,} CS)"
        if current_lower and current_lower not in label.lower():
            continue
        if len(label) > 100:
            label = label[:97] + "..."
        choices.append(app_commands.Choice(name=label, value=str(r['id'])))
        if len(choices) >= 25:
            break
    return choices
