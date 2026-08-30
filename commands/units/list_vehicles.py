# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import json
import discord
from discord import app_commands
from discord.ui import View, Select, Button
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from utils.views import OwnerOnlyView
from services.vehicle_service import list_vehicles as list_vehicles_service, get_vehicle_details
from services.validation_service import require_faction

VEHICLES_PER_PAGE = 10


def _parse_specs(specs) -> list[str]:
    spec_data = None
    if isinstance(specs, list) and specs:
        spec_data = json.loads(specs[0]) if isinstance(specs[0], str) else specs[0]
    elif isinstance(specs, dict):
        spec_data = specs

    if not spec_data:
        return []

    lines = []
    for key, label in [('length', None), ('engines', 'Engines'), ('flight_type', 'Flight Type'),
                        ('aircraft_type', 'Type'), ('ftl', 'FTL'), ('main', 'Main Weapons'),
                        ('secondary', 'Secondary'), ('lances', 'Lances'), ('pdc', 'PDC'),
                        ('torpedoes', 'Torpedoes'), ('guns', 'Guns'), ('heavy', 'Heavy'),
                        ('medium', 'Medium'), ('light', 'Light'), ('rocket', 'Rockets'),
                        ('ordnance_kg', None), ('cargo', 'Cargo'), ('systems', 'Systems'),
                        ('speed_mach', None)]:
        val = spec_data.get(key)
        if not val:
            continue
        if key == 'length':
            lines.append(f"Length: {val}m")
        elif key == 'ordnance_kg':
            lines.append(f"Ordnance: {val}kg")
        elif key == 'speed_mach':
            lines.append(f"Speed: Mach {val}")
        elif key in ('flight_type', 'aircraft_type'):
            lines.append(f"{label}: {str(val).title()}")
        else:
            lines.append(f"{label}: {val}")

    for key, label in [('armor', 'Armor'), ('protection', 'Protection'), ('stealth', 'Stealth')]:
        val = spec_data.get(key)
        if val and val != 'none':
            lines.append(label if isinstance(val, bool) else f"{label}: {str(val).title()}")

    for key, label in [('boat', 'Sea Boat'), ('weapons', 'Armed'), ('shield', 'Shielded'),
                        ('helicopter', 'Helicopter'), ('drone', 'Drone')]:
        if spec_data.get(key):
            lines.append(label)

    if spec_data.get('radar') == 'AEW':
        lines.append("AEW Radar")
    cap = spec_data.get('capability')
    if cap and cap != 'none':
        lines.append(cap)

    return lines


class VehicleDetailView(View):
    def __init__(self, embed_data: dict, user_id: int, original_view: 'VehiclePaginationView' = None):
        super().__init__(timeout=180)
        self.embed_data = embed_data
        self.user_id = user_id
        self.original_view = original_view
        self.hidden = False

    def create_embed(self) -> discord.Embed:
        if self.hidden:
            return discord.Embed(
                title=self.embed_data['title'],
                description="[HIDDEN]",
                color=self.embed_data['color']
            )
        embed = discord.Embed(
            title=self.embed_data['title'],
            description=self.embed_data['description'],
            color=self.embed_data['color']
        )
        for field in self.embed_data['fields']:
            embed.add_field(name=field['name'], value=field['value'], inline=field.get('inline', True))
        return embed

    @discord.ui.button(label="◀ Back to List", style=discord.ButtonStyle.secondary, row=0)
    async def back_button(self, interaction: discord.Interaction, _: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your vehicle list."))
            return
        if not self.original_view:
            await interaction.response.send_message(embed=error_embed("Error", "No list to go back to."))
            return
        await interaction.response.edit_message(embed=self.original_view.get_embed(), view=self.original_view)

    @discord.ui.button(label="Hide", style=discord.ButtonStyle.secondary, row=0)
    async def hide_button(self, interaction: discord.Interaction, button: Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your vehicle view."))
            return
        self.hidden = not self.hidden
        button.label = "Show" if self.hidden else "Hide"
        await interaction.response.edit_message(embed=self.create_embed(), view=self)


class VehiclePageJumpModal(discord.ui.Modal, title="Jump to Page"):
    page_number = discord.ui.TextInput(
        label="Page Number",
        placeholder="Enter page number...",
        required=True,
        max_length=5
    )

    def __init__(self, vehicle_view):
        super().__init__()
        self.vehicle_view = vehicle_view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            page = int(self.page_number.value) - 1
            if page < 0 or page >= self.vehicle_view.total_pages:
                page = 0
            self.vehicle_view.page = page
            self.vehicle_view.add_selectors()
            await interaction.response.edit_message(embed=self.vehicle_view.get_embed(), view=self.vehicle_view)
        except ValueError:
            await interaction.response.send_message(embed=error_embed("Error", "Please enter a valid page number."))


class VehiclePaginationView(OwnerOnlyView):
    def __init__(self, owner_id: int, vehicles: list, faction_data: dict, page: int = 0):
        super().__init__(owner_id=owner_id, timeout=180)
        self.vehicles = vehicles
        self.faction_data = faction_data
        self.page = page
        self.total_pages = (len(vehicles) - 1) // VEHICLES_PER_PAGE + 1
        self.hidden = False
        self.vehicle_select = None
        self.add_selectors()

    def add_selectors(self):
        if self.vehicle_select:
            self.remove_item(self.vehicle_select)

        start = self.page * VEHICLES_PER_PAGE
        page_vehicles = self.vehicles[start:start + VEHICLES_PER_PAGE]

        options = []
        for v in page_vehicles:
            vname = v['name']
            if v['designation']:
                vname += f" {v['designation']}"
            options.append(discord.SelectOption(
                label=f"#{v['faction_vehicle_number']} - {vname}"[:100],
                description=f"Type: {v['type_name']}"[:100],
                value=str(v['id'])
            ))

        self.vehicle_select = Select(placeholder="Select a vehicle to view details...", options=options, row=0)
        self.vehicle_select.callback = self.vehicle_selected
        self.add_item(self.vehicle_select)

    async def vehicle_selected(self, interaction: discord.Interaction):
        vehicle_id = int(self.vehicle_select.values[0])
        full_vehicle, costs, units_with_vehicle = await get_vehicle_details(vehicle_id)

        display_name = full_vehicle.name
        if full_vehicle.designation:
            display_name += f" {full_vehicle.designation}"

        faction_color = hex_to_int(self.faction_data.color)
        embed_data = {
            'title': display_name,
            'description': f"**Faction Vehicle Number:** #{full_vehicle.faction_vehicle_number}",
            'color': faction_color,
            'fields': [
                {'name': 'Type',    'value': full_vehicle.type_name or "Unclassified", 'inline': True},
                {'name': 'Faction', 'value': self.faction_data.display_name,           'inline': True},
            ]
        }

        if costs:
            embed_data['fields'].append({
                'name': 'Cost (per unit)',
                'value': "\n".join(f"**{c.name}:** {handle_return(c.amount)}" for c in costs),
                'inline': False
            })

        spec_lines = _parse_specs(full_vehicle.vehicle_data)
        if spec_lines:
            embed_data['fields'].append({'name': 'Specifications', 'value': " | ".join(spec_lines), 'inline': False})

        if units_with_vehicle:
            total = sum(uv['amount'] for uv in units_with_vehicle)
            unit_lines = [f"**{uv['fleet_name'] or 'Unit #' + str(uv['faction_fleet_number'])}:** {uv['amount']:,}" for uv in units_with_vehicle]
            value = "\n".join(unit_lines[:10]) + ("\n..." if len(unit_lines) > 10 else "")
            embed_data['fields'].append({'name': f"In Service ({total:,} total)", 'value': value, 'inline': False})
        else:
            embed_data['fields'].append({'name': 'In Service', 'value': 'None deployed', 'inline': False})

        detail_view = VehicleDetailView(embed_data, self.owner_id, self)
        await interaction.response.edit_message(embed=detail_view.create_embed(), view=detail_view)

    def get_embed(self) -> discord.Embed:
        start = self.page * VEHICLES_PER_PAGE
        page_vehicles = self.vehicles[start:start + VEHICLES_PER_PAGE]
        embed = discord.Embed(
            title=f"Vehicles: {self.faction_data.display_name}",
            description=f"Page {self.page + 1}/{self.total_pages} • {len(self.vehicles)} total vehicles",
            color=hex_to_int(self.faction_data.color)
        )

        if self.hidden:
            embed.add_field(name="Content Hidden", value="[HIDDEN]", inline=False)
            return embed

        for vehicle in page_vehicles:
            costs_raw = vehicle['costs']
            costs_list = json.loads(costs_raw) if isinstance(costs_raw, str) else (costs_raw or [])
            cost_str = ", ".join(f"{handle_return(c['amount'])} {c['resource']}" for c in costs_list) if costs_list else "No cost defined"
            designation = f" [{vehicle['designation']}]" if vehicle['designation'] else ""
            type_name = vehicle['type_name'] or "Unknown Type"
            embed.add_field(
                name=f"#{vehicle['faction_vehicle_number']}: {vehicle['name']}{designation}",
                value=f"**Type:** {type_name}\n**Cost:** {cost_str}\n​",
                inline=False
            )
        embed.set_footer(text="Select a vehicle from the dropdown to view details")
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, row=1)
    async def prev_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page = (self.page - 1) % self.total_pages
        self.add_selectors()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Jump to Page", style=discord.ButtonStyle.primary, row=1)
    async def jump_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.send_modal(VehiclePageJumpModal(self))

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=1)
    async def next_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.page = (self.page + 1) % self.total_pages
        self.add_selectors()
        await interaction.response.edit_message(embed=self.get_embed(), view=self)

    @discord.ui.button(label="Hide", style=discord.ButtonStyle.secondary, row=2)
    async def hide_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.hidden = not self.hidden
        button.label = "Show" if self.hidden else "Hide"
        self.vehicle_select.disabled = self.hidden
        await interaction.response.edit_message(embed=self.get_embed(), view=self)


@app_commands.command(name="list", description="List all vehicles for a faction")
@app_commands.describe(faction="Faction name")
@require_access_level(0)
@ephemeral_capable('faction')
async def list_vehicles(interaction: discord.Interaction, faction: str):
    await defer_response(interaction)

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok:
        await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
        return
    faction_data = r_faction_data.data

    vehicles = await list_vehicles_service(faction_data.id)

    if not vehicles:
        await interaction.followup.send(embed=error_embed("Error", f"No vehicles found for {faction_data.display_name}."))
        return

    view = VehiclePaginationView(interaction.user.id, list(vehicles), faction_data)
    await interaction.followup.send(embed=view.get_embed(), view=view)


async def setup(bot):
    bot.tree.add_command(list_vehicles)
