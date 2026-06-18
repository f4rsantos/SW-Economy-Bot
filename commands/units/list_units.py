import asyncio
import math
import discord
from discord import app_commands
from discord.ui import View, Select
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.fleet_service import get_fleets, get_fleet, get_fleet_vehicles, get_unit_vehicle_resource_totals
from services.map_service import search_world_names
from services.faction_service import search_faction_names
from utils.currency import handle_return
from services.validation_service import require_faction, require_world

UNITS_PER_PAGE = 10

UPKEEP_DIVISORS = {
    'idle': 8, 'defense': 6, 'patrol': 6,
    'battle': 4, 'debris': 0
}


def calculate_unit_upkeep(total_cs: int, status: str) -> int:
    divisor = UPKEEP_DIVISORS.get(status.lower(), 8)
    return 0 if divisor == 0 else math.ceil(total_cs / divisor)


class UnitDetailView(View):
    def __init__(self, unit_data: dict, vehicles: list, faction_name: str, user_id: int,
                 faction_color: int, all_units: list, faction_id: int, world_mode: bool = False,
                 vehicle_resource_totals: dict = None):
        super().__init__(timeout=180)
        self.unit_data = unit_data
        self.vehicles = vehicles
        self.faction_name = faction_name
        self.user_id = user_id
        self.faction_color = faction_color
        self.all_units = all_units
        self.faction_id = faction_id
        self.world_mode = world_mode
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

        type_label = self.unit_data.get('type_name') or "Unclassified"
        embed = discord.Embed(title=unit_name, description=f"Unit #{self.unit_data['faction_fleet_number']}", color=self.faction_color)
        embed.add_field(name="Faction",        value=self.faction_name,                   inline=True)
        embed.add_field(name="Type",           value=type_label,                           inline=True)
        embed.add_field(name="Status",         value=self.unit_data['status'],             inline=True)
        embed.add_field(name="Position",       value=position_text,                        inline=True)
        embed.add_field(name="Health",         value=f"{self.unit_data['health']}%",       inline=True)
        embed.add_field(name="Total CS",          value=f"{self.unit_data['total_cs']:,}", inline=True)
        res_str = "\n".join(f"**{name}:** {handle_return(amt)}" for name, amt in self.vehicle_resource_totals.items()) if self.vehicle_resource_totals else "None"
        embed.add_field(name="Total Resources", value=res_str,                            inline=True)
        embed.add_field(name="Upkeep",         value=f"{upkeep:,} CS/week",                inline=True)
        infantry = self.unit_data.get('infantry_count', 0)
        if infantry:
            embed.add_field(name="Infantry",   value=f"{infantry:,}",                      inline=True)

        if self.vehicles:
            lines = []
            for v in self.vehicles:
                display = f"{v['vehicle_name']} {v['designation']}" if v['designation'] else v['vehicle_name']
                lines.append(f"**{display} ({v['faction_vehicle_number']})**: {v['amount']:,}")
            embed.add_field(name="Vehicles", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Vehicles", value="No vehicles in this unit", inline=False)

        return embed

    @discord.ui.button(label="◀ Back to List", style=discord.ButtonStyle.secondary, row=0)
    async def back_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your unit list."), ephemeral=True)
            return
        view = UnitView(self.all_units, self.faction_id, self.faction_name, self.user_id, self.faction_color, world_mode=self.world_mode)
        await interaction.response.edit_message(embed=await view.create_list_embed(), view=view)

    @discord.ui.button(label="Hide", style=discord.ButtonStyle.secondary, row=0)
    async def hide_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your unit list."), ephemeral=True)
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
            await interaction.response.send_message(embed=error_embed("Error", "Please enter a valid page number."), ephemeral=True)


class UnitView(View):
    def __init__(self, units: list, faction_id: int, faction_name: str, user_id: int,
                 faction_color: int = 0x2ecc71, world_mode: bool = False):
        super().__init__(timeout=180)
        self.units = units
        self.faction_id = faction_id
        self.faction_name = faction_name
        self.user_id = user_id
        self.faction_color = faction_color
        self.world_mode = world_mode
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
            uname = u['name'] or f"Unit #{u['faction_fleet_number']}"
            options.append(discord.SelectOption(
                label=f"#{u['faction_fleet_number']} - {uname}"[:100],
                description=f"{u['status']} at {u['position']}"[:100],
                value=str(u['id'])
            ))
        self.unit_select = Select(placeholder="Select a unit to view details...", options=options, row=0)
        self.unit_select.callback = self.unit_selected
        self.add_item(self.unit_select)

    async def unit_selected(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your unit list."), ephemeral=True)
            return

        unit_id = int(self.unit_select.values[0])
        unit_row, vehicles, vehicle_resource_totals = await asyncio.gather(
            get_fleet(unit_id),
            get_fleet_vehicles(unit_id),
            get_unit_vehicle_resource_totals(unit_id)
        )
        if not unit_row:
            await interaction.response.send_message(embed=error_embed("Error", "Unit not found."), ephemeral=True)
            return

        unit_data = {
            'id': unit_row['id'],
            'name': unit_row['name'],
            'faction_fleet_number': unit_row['faction_fleet_number'],
            'status': unit_row['status_name'],
            'position': unit_row['position_name'],
            'moving_to_name': unit_row.get('moving_to_name'),
            'health': unit_row['health'],
            'total_cs': unit_row['total_cs'],
            'type_name': unit_row.get('type_name'),
            'infantry_count': unit_row.get('infantry_count', 0),
        }

        detail_view = UnitDetailView(unit_data, vehicles, self.faction_name,
                                     self.user_id, self.faction_color, self.units,
                                     self.faction_id, world_mode=self.world_mode,
                                     vehicle_resource_totals=vehicle_resource_totals)
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
            unit_name = unit['name'] or f"Unit #{unit['faction_fleet_number']}"
            upkeep = calculate_unit_upkeep(unit['total_cs'], unit['status'])
            position_text = unit['position']
            if unit.get('moving_to_name'):
                position_text = f"{unit['position']} → **{unit['moving_to_name']}**"
            info = (
                f"**ID:** #{unit['faction_fleet_number']}\n"
                + (f"**Faction:** {unit['faction_name']}\n" if self.world_mode else "")
                + f"**Status:** {unit['status']}\n"
                f"**Position:** {position_text}\n"
                f"**Health:** {unit['health']}%\n"
                f"**Upkeep:** {upkeep:,}/week"
            )
            embed.add_field(name=unit_name, value=info, inline=False)
        embed.set_footer(text="Select a unit from the dropdown to view details")
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, row=1)
    async def prev_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your unit list."), ephemeral=True)
            return
        self.page = (self.page - 1) % self.total_pages
        self.add_unit_selector()
        await interaction.response.edit_message(embed=await self.create_list_embed(), view=self)

    @discord.ui.button(label="Jump to Page", style=discord.ButtonStyle.primary, row=1)
    async def jump_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your unit list."), ephemeral=True)
            return
        await interaction.response.send_modal(PageJumpModal(self))

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, row=1)
    async def next_button(self, interaction: discord.Interaction, _: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your unit list."), ephemeral=True)
            return
        self.page = (self.page + 1) % self.total_pages
        self.add_unit_selector()
        await interaction.response.edit_message(embed=await self.create_list_embed(), view=self)

    @discord.ui.button(label="Hide", style=discord.ButtonStyle.secondary, row=1)
    async def hide_list_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(embed=error_embed("Error", "This is not your unit list."), ephemeral=True)
            return
        self.hidden = not self.hidden
        button.label = "Show" if self.hidden else "Hide"
        self.unit_select.disabled = self.hidden
        await interaction.response.edit_message(embed=await self.create_list_embed(), view=self)


async def faction_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
    names = await search_faction_names(current)
    return [app_commands.Choice(name=name, value=name) for name in names]


@app_commands.command(name="list", description="List units (filter by faction, world, or both)")
@app_commands.describe(
    faction="Filter by Faction name (optional)",
    world="Filter by World name (optional)"
)
@require_access_level(0)
async def list_units(interaction: discord.Interaction, faction: str = None, world: str = None):
    if not faction and not world:
        await interaction.response.send_message(embed=error_embed("Error", "You must provide at least a Faction OR a World."), ephemeral=True)
        return

    faction_data = None
    world_data = None
    if faction and world:
        r_faction_data, r_world = await asyncio.gather(require_faction(faction), require_world(world))
        if not r_faction_data.ok:
            await interaction.response.send_message(embed=error_embed("Error", r_faction_data.error), ephemeral=True)
            return
        if not r_world.ok:
            await interaction.response.send_message(embed=error_embed("Error", r_world.error), ephemeral=True)
            return
        faction_data = r_faction_data.data
        world_data = r_world.data
    elif faction:
        r_faction_data = await require_faction(faction)
        if not r_faction_data.ok:
            await interaction.response.send_message(embed=error_embed("Error", r_faction_data.error), ephemeral=True)
            return
        faction_data = r_faction_data.data
    elif world:
        r_world = await require_world(world)
        if not r_world.ok:
            await interaction.response.send_message(embed=error_embed("Error", r_world.error), ephemeral=True)
            return
        world_data = r_world.data

    faction_id = faction_data['id'] if faction_data else None
    world_id = world_data['id'] if world_data else None
    units = await get_fleets(faction_id=faction_id, world_id=world_id)

    if not units:
        await interaction.response.send_message(embed=error_embed("No Units Found", "No units found matching the given filters."), ephemeral=True)
        return

    if faction_data:
        view_name = faction_data['display_name']
        view_color = hex_to_int(faction_data['color'])
        view_faction_id = faction_data['id']
        world_mode = False
    else:
        view_name = f"Units at {world_data['name']}"
        view_color = 0x95a5a6
        view_faction_id = 0
        world_mode = True

    view = UnitView(list(units), view_faction_id, view_name, interaction.user.id, view_color, world_mode=world_mode)
    await interaction.response.send_message(embed=await view.create_list_embed(), view=view)


async def setup(bot):
    list_units.autocomplete('faction')(faction_autocomplete)

    async def world_autocomplete(_: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
        names = await search_world_names(current)
        return [app_commands.Choice(name=name, value=name) for name in names]

    list_units.autocomplete('world')(world_autocomplete)
    bot.tree.add_command(list_units)
