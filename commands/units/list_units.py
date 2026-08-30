# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import asyncio
import math
import discord
from typing import Optional
from discord import app_commands
from discord.ui import View, Select
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import error_embed, progress_bar
from utils.faction_utils import hex_to_int
from services.fleet_service import get_fleets, get_fleet, get_fleet_vehicles, get_unit_vehicle_resource_totals
from utils.autocomplete import faction_autocomplete, world_autocomplete
from utils.currency import handle_return
from services.validation_service import require_faction, require_world
from services.travel_time_service import calculate_travel_time
from services.user_service import get_user_access_level
from services.intelligence_service import (
    get_foreign_shared_worlds,
    is_foreign_visible,
    get_user_faction_id,
    has_presence_at_world,
    get_observed_worlds,
    filter_visible_vehicles,
)

UNITS_PER_PAGE = 10

UPKEEP_DIVISORS = {
    'idle': 8, 'defence': 6, 'patrol': 6,
    'battle': 4, 'debris': 0
}


def calculate_unit_upkeep(total_cs: int, status: str) -> int:
    divisor = UPKEEP_DIVISORS.get(status.lower(), 8)
    return 0 if divisor == 0 else math.ceil(total_cs / divisor)


async def get_arrival_timestamp(origin_name: str, destination_name: str, moving_since) -> Optional[int]:
    if not origin_name or not destination_name or not moving_since:
        return None
    travel_duration = await calculate_travel_time(origin_name, destination_name, moving_since)
    arrival_time = moving_since + travel_duration
    return int(arrival_time.timestamp())


class UnitDetailView(View):
    def __init__(self, unit_data: dict, vehicles: list, faction_name: str, user_id: int,
                 faction_color: int, all_units: list, faction_id: int, world_mode: bool = False,
                 vehicle_resource_totals: dict = None, hidden_count: int = 0, ref_mode: bool = False,
                 viewer_faction_id: int = None):
        super().__init__(timeout=180)
        self.viewer_faction_id = viewer_faction_id
        self.unit_data = unit_data
        self.vehicles = vehicles
        self.faction_name = faction_name
        self.user_id = user_id
        self.faction_color = faction_color
        self.all_units = all_units
        self.faction_id = faction_id
        self.world_mode = world_mode
        self.hidden_count = hidden_count
        self.ref_mode = ref_mode
        self.hidden = False
        self.vehicle_resource_totals = vehicle_resource_totals or {}

    async def create_detail_embed(self) -> discord.Embed:
        unit_name = self.unit_data['name'] or f"Unit #{self.unit_data['faction_fleet_number']}"
        if self.hidden:
            return discord.Embed(title=unit_name, description="[HIDDEN]", color=self.faction_color)

        upkeep = calculate_unit_upkeep(self.unit_data['total_cs'], self.unit_data['status'])
        position_text = self.unit_data['position']
        if self.unit_data.get('moving_to_name'):
            position_text = f"{self.unit_data['position']} → **{self.unit_data['moving_to_name']}**"
            arrival_ts = await get_arrival_timestamp(
                self.unit_data['position'], self.unit_data['moving_to_name'], self.unit_data.get('moving_since')
            )
            if arrival_ts:
                position_text += f" (arrives <t:{arrival_ts}:R>)"

        type_label = self.unit_data.get('type_name') or "Unclassified"
        infantry = self.unit_data.get('infantry_count', 0)
        health = self.unit_data['health']

        fields = [
            {'name': "Type", 'value': type_label, 'inline': True},
            {'name': "Total CS", 'value': f"{self.unit_data['total_cs']:,}", 'inline': True},
            {'name': "Upkeep", 'value': f"{upkeep:,} CS/week", 'inline': True},
        ]
        if infantry:
            fields.append({'name': "Infantry", 'value': f"{infantry:,}", 'inline': True})

        if self.vehicle_resource_totals:
            worth = "\n".join(f"{handle_return(amt)} {name}" for name, amt in self.vehicle_resource_totals.items())
            fields.append({'name': "Worth", 'value': worth, 'inline': True})

        if self.vehicles:
            lines = []
            for v in self.vehicles:
                display = f"{v['vehicle_name']} {v['designation']}" if v['designation'] else v['vehicle_name']
                lines.append(f"{v['amount']:,}x {display} (#{v['faction_vehicle_number']})")
            if self.hidden_count:
                lines.append(f"{self.hidden_count:,} not identified")
            fields.append({'name': "Vehicles", 'value': "\n".join(lines), 'inline': False})
        elif self.hidden_count:
            fields.append({'name': "Vehicles", 'value': f"{self.hidden_count:,} not identified", 'inline': False})
        else:
            fields.append({'name': "Vehicles", 'value': "No vehicles assigned", 'inline': False})

        embed = discord.Embed(title=unit_name, color=self.faction_color)
        embed.description = (
            f"**Faction:** {self.faction_name}\n"
            f"**ID:** #{self.unit_data['faction_fleet_number']}\n"
            f"**Status:** {self.unit_data['status']}\n"
            f"**Position:** {position_text}\n"
            f"**Health:** `{progress_bar(health, 100)}` {health}%"
        )
        for field in fields:
            embed.add_field(name=field['name'], value=field['value'], inline=field['inline'])
        return embed

    @discord.ui.button(label="◀ Back to List", style=discord.ButtonStyle.secondary, row=0)
    async def back_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your unit list."))
            return
        view = UnitView(self.all_units, self.faction_id, self.faction_name, self.user_id,
                        self.faction_color, world_mode=self.world_mode,
                        viewer_faction_id=self.viewer_faction_id, ref_mode=self.ref_mode)
        await interaction.response.edit_message(embed=await view.create_list_embed(), view=view)

    @discord.ui.button(label="Hide", style=discord.ButtonStyle.secondary, row=0)
    async def hide_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your unit list."))
            return
        self.hidden = not self.hidden
        button.label = "Show" if self.hidden else "Hide"
        await interaction.response.edit_message(embed=await self.create_detail_embed(), view=self)


class PageJumpModal(discord.ui.Modal, title="Jump to Page"):
    page_number = discord.ui.TextInput(label="Page Number", placeholder="Enter page number...", required=True, max_length=5)

    def __init__(self, unit_view):
        super().__init__()
        self.unit_view = unit_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page_number.value) - 1
            if page < 0 or page >= self.unit_view.total_pages:
                page = 0
            self.unit_view.page = page
            self.unit_view.add_unit_selector()
            await interaction.response.edit_message(embed=await self.unit_view.create_list_embed(), view=self.unit_view)
        except ValueError:
            await interaction.response.send_message(embed=error_embed("Error", "Please enter a valid page number."))


class UnitView(View):
    def __init__(self, units: list, faction_id: int, faction_name: str, user_id: int,
                 faction_color: int = 0x2ecc71, world_mode: bool = False,
                 viewer_faction_id: int = None, ref_mode: bool = False):
        super().__init__(timeout=180)
        self.units = units
        self.faction_id = faction_id
        self.faction_name = faction_name
        self.user_id = user_id
        self.faction_color = faction_color
        self.world_mode = world_mode
        self.viewer_faction_id = viewer_faction_id
        self.ref_mode = ref_mode
        self.page = 0
        self.hidden = False
        self.total_pages = (len(units) - 1) // UNITS_PER_PAGE + 1
        self.unit_select = None
        self.add_unit_selector()

    def add_unit_selector(self):
        if self.unit_select:
            self.remove_item(self.unit_select)
        start = self.page * UNITS_PER_PAGE
        page_units = self.units[start:start + UNITS_PER_PAGE]
        options = []
        for u in page_units:
            uname = u.name or f"Unit #{u.faction_fleet_number}"
            options.append(discord.SelectOption(
                label=f"#{u.faction_fleet_number} - {uname}"[:100],
                description=f"{u.status} at {u.position}"[:100],
                value=str(u.id)
            ))
        self.unit_select = Select(placeholder="Select a unit to view details...", options=options, row=0)
        self.unit_select.callback = self.unit_selected
        self.add_item(self.unit_select)

    async def unit_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your unit list."))
            return

        unit_id = int(self.unit_select.values[0])
        unit_row, vehicles, vehicle_resource_totals = await asyncio.gather(
            get_fleet(unit_id),
            get_fleet_vehicles(unit_id),
            get_unit_vehicle_resource_totals(unit_id)
        )
        if not unit_row:
            await interaction.response.send_message(embed=error_embed("Error", "Unit not found."))
            return

        unit_data = {
            'id': unit_row.id,
            'name': unit_row.name,
            'faction_fleet_number': unit_row.faction_fleet_number,
            'status': unit_row.status_name,
            'position': unit_row.position_name,
            'moving_to_name': unit_row.moving_to_name,
            'moving_since': unit_row.moving_since,
            'health': unit_row.health,
            'total_cs': unit_row.total_cs,
            'type_name': unit_row.type_name,
            'infantry_count': unit_row.infantry_count or 0,
        }

        is_own = self.ref_mode or (
            self.viewer_faction_id is not None and unit_row.faction_id == self.viewer_faction_id
        )
        vehicles, hidden_count = filter_visible_vehicles(
            [dict(v) for v in vehicles], is_own, unit_row.status_name
        )

        detail_view = UnitDetailView(unit_data, vehicles, self.faction_name,
                                     self.user_id, self.faction_color, self.units,
                                     self.faction_id, world_mode=self.world_mode,
                                     vehicle_resource_totals=vehicle_resource_totals,
                                     hidden_count=hidden_count, ref_mode=self.ref_mode,
                                     viewer_faction_id=self.viewer_faction_id)
        await interaction.response.edit_message(embed=await detail_view.create_detail_embed(), view=detail_view)

    async def create_list_embed(self) -> discord.Embed:
        if self.hidden:
            return discord.Embed(title=f"Units: {self.faction_name}", description="[HIDDEN]", color=self.faction_color)

        start = self.page * UNITS_PER_PAGE
        page_units = self.units[start:start + UNITS_PER_PAGE]
        embed = discord.Embed(
            title=f"Units: {self.faction_name}",
            description=f"Page {self.page + 1}/{self.total_pages} • {len(self.units)} total units",
            color=self.faction_color
        )
        for unit in page_units:
            unit_name = unit.name or f"Unit #{unit.faction_fleet_number}"
            upkeep = calculate_unit_upkeep(unit.total_cs, unit.status)
            position_text = unit.position
            if unit.moving_to_name:
                position_text = f"{unit.position} → **{unit.moving_to_name}**"
                arrival_ts = await get_arrival_timestamp(unit.position, unit.moving_to_name, unit.moving_since)
                if arrival_ts:
                    position_text += f" <t:{arrival_ts}:R>"
            info = (
                f"**ID:** #{unit.faction_fleet_number}\n"
                + (f"**Faction:** {unit.faction_name}\n" if self.world_mode else "")
                + f"**Status:** {unit.status}\n"
                f"**Position:** {position_text}\n"
                f"**Health:** `{progress_bar(unit.health, 100)}` {unit.health}%\n"
                f"**Upkeep:** {upkeep:,}/week"
                "\n​"
            )
            embed.add_field(name=unit_name, value=info, inline=False)
        embed.set_footer(text="Select a unit from the dropdown to view details")
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, row=1)
    async def prev_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your unit list."))
            return
        self.page = (self.page - 1) % self.total_pages
        self.add_unit_selector()
        await interaction.response.edit_message(embed=await self.create_list_embed(), view=self)

    @discord.ui.button(label="Jump to Page", style=discord.ButtonStyle.primary, row=1)
    async def jump_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your unit list."))
            return
        await interaction.response.send_modal(PageJumpModal(self))

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=1)
    async def next_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your unit list."))
            return
        self.page = (self.page + 1) % self.total_pages
        self.add_unit_selector()
        await interaction.response.edit_message(embed=await self.create_list_embed(), view=self)

    @discord.ui.button(label="Hide", style=discord.ButtonStyle.secondary, row=1)
    async def hide_list_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your unit list."))
            return
        self.hidden = not self.hidden
        button.label = "Show" if self.hidden else "Hide"
        self.unit_select.disabled = self.hidden
        await interaction.response.edit_message(embed=await self.create_list_embed(), view=self)


REF_ACCESS_LEVEL = 4


@app_commands.command(name="list", description="List units (filter by faction, world, or both)")
@app_commands.describe(
    faction="Filter by Faction name (optional)",
    world="Filter by World name (optional)",
    ref="Referee mode: see every unit in full. Never private."
)
@require_access_level(0)
@ephemeral_capable('faction')
async def list_units(interaction: discord.Interaction, faction: str = None, world: str = None, ref: bool = False):
    if ref:
        interaction.extras['ephemeral'] = False
        await interaction.response.defer()
    else:
        await defer_response(interaction)

    if not faction and not world:
        await interaction.followup.send(embed=error_embed("Error", "You must provide at least a Faction OR a World."))
        return

    if ref:
        viewer_level = await get_user_access_level(interaction.user.id)
        if viewer_level < REF_ACCESS_LEVEL:
            await interaction.followup.send(embed=error_embed("Error", "Referee mode requires elevated access."))
            return

    viewer_faction_id = None if ref else await get_user_faction_id(interaction.user.id)

    faction_data = None
    world_data = None
    if faction and world:
        r_faction_data, r_world = await asyncio.gather(require_faction(faction), require_world(world))
        if not r_faction_data.ok:
            await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
            return
        if not r_world.ok:
            await interaction.followup.send(embed=error_embed("Error", r_world.error))
            return
        faction_data = r_faction_data.data
        world_data = r_world.data
    elif faction:
        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok:
            await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
            return
        faction_data = r_faction_data.data
    elif world:
        r_world = await require_world(world)
        if not r_world.ok:
            await interaction.followup.send(embed=error_embed("Error", r_world.error))
            return
        world_data = r_world.data

    faction_id = faction_data.id if faction_data else None
    world_id = world_data['id'] if world_data else None

    if not ref:
        if viewer_faction_id is None:
            await interaction.followup.send(embed=error_embed(
                "Intelligence insufficient",
                "You do not lead a faction. Use `ref:true` to view units openly."
            ))
            return

        if faction_id is not None and faction_id != viewer_faction_id:
            await interaction.followup.send(embed=error_embed(
                "Intelligence insufficient",
                "You can only look up your own faction. Use `ref:true` to view another faction openly."
            ))
            return

        if world_id is not None and not await has_presence_at_world(viewer_faction_id, world_id):
            await interaction.followup.send(embed=error_embed(
                "Intelligence insufficient",
                "You have no units or territory at this world."
            ))
            return

    units = await get_fleets(faction_id=faction_id, world_id=world_id)

    if not ref:
        observed = await get_observed_worlds(viewer_faction_id)
        foreign_worlds = await get_foreign_shared_worlds(viewer_faction_id)
        units = [
            u for u in units
            if u.faction_id == viewer_faction_id
            or u.position_id in observed
            or is_foreign_visible(foreign_worlds, u.position_id, u.faction_id)
        ]

    if not units:
        await interaction.followup.send(embed=error_embed("No Units Found", "No units found matching the given filters."))
        return

    if faction_data:
        view_name = faction_data.display_name
        view_color = hex_to_int(faction_data.color)
        view_faction_id = faction_data.id
        world_mode = False
    else:
        view_name = f"Units at {world_data['name']}"
        view_color = 0x95a5a6
        view_faction_id = 0
        world_mode = True

    view = UnitView(list(units), view_faction_id, view_name, interaction.user.id, view_color,
                    world_mode=world_mode, viewer_faction_id=viewer_faction_id, ref_mode=ref)
    await interaction.followup.send(embed=await view.create_list_embed(), view=view)


async def setup(bot):
    list_units.autocomplete('faction')(faction_autocomplete)
    list_units.autocomplete('world')(world_autocomplete)
    bot.tree.add_command(list_units)
