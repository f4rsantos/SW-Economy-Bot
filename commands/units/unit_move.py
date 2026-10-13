# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

import discord
from discord import app_commands
from datetime import datetime, timezone, timedelta
from utils.checks import require_access_level, ephemeral_capable, defer_response
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from utils.views import OwnerOnlyView
from services.travel_time_service import calculate_travel_time, format_travel_time
from services.fleet_service import move_fleet
from utils.autocomplete import faction_autocomplete
from services.validation_service import require_faction, require_unit, require_world
from services import port_service
from database.static_cache import static_cache


async def execute_move(unit_data, dest_data: dict, faction_id: int, faction_color: int, use_lanes: bool) -> discord.Embed:
    was_blockading = unit_data['status_name'].lower() == 'blockading'

    now = datetime.now(timezone.utc)
    route_info = None
    if use_lanes:
        route_info = await port_service.calculate_best_route(
            unit_data['position'], unit_data['world_name'], dest_data['id'], dest_data['name'],
            faction_id, port_service.TRAFFIC_UNITS,
        )
        travel_duration = route_info['duration']
    else:
        travel_duration = await calculate_travel_time(unit_data['world_name'], dest_data['name'])
    arrival_time = now + travel_duration

    try:
        await move_fleet(unit_data['id'], dest_data['id'], now)
    except ValueError as e:
        return error_embed("Error", str(e))

    from services.event_queue import event_queue
    await event_queue.push(arrival_time, 'fleet_arrival', {'fleet_id': unit_data['id'], 'to_world_id': dest_data['id']})

    unit_name = unit_data['name'] or f"Unit #{unit_data['faction_fleet_number']}"
    travel_time_str = await format_travel_time(travel_duration)

    blockade_note = "\nUnit left its blockade." if was_blockading else ""
    embed = discord.Embed(
        title="Unit Movement Initiated",
        description=f"**{unit_name}** is now traveling.{blockade_note}",
        color=faction_color
    )
    embed.add_field(name="From", value=unit_data['world_name'], inline=True)
    embed.add_field(name="To", value=dest_data['name'], inline=True)
    embed.add_field(name="Travel Time", value=travel_time_str, inline=True)
    embed.add_field(name="Arrival", value=f"<t:{int(arrival_time.timestamp())}:R>", inline=False)

    if route_info and route_info['used_lanes']:
        from services.map_service import get_worlds_by_ids
        path_worlds = await get_worlds_by_ids(route_info['world_path'])
        path_names_by_id = {w['id']: w['name'] for w in path_worlds}
        path_names = [path_names_by_id.get(wid, str(wid)) for wid in route_info['world_path']]
        saving_str = await format_travel_time(timedelta(seconds=route_info['saving_seconds']))
        embed.add_field(
            name="Route",
            value=f"Via lanes through {' then '.join(path_names)}, saving {saving_str}",
            inline=False,
        )

    return embed


class CrossSystemMoveView(OwnerOnlyView):
    def __init__(self, owner_id: int, unit_data, dest_data: dict, faction_id: int, faction_color: int, use_lanes: bool):
        super().__init__(owner_id)
        self.unit_data = unit_data
        self.dest_data = dest_data
        self.faction_id = faction_id
        self.faction_color = faction_color
        self.use_lanes = use_lanes

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, _: discord.ui.Button):
        await interaction.response.defer()
        embed = await execute_move(self.unit_data, self.dest_data, self.faction_id, self.faction_color, self.use_lanes)
        self.stop()
        await interaction.edit_original_response(embed=embed, view=None)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.stop()
        embed = discord.Embed(title="Movement Cancelled", description="The unit stays where it is.", color=self.faction_color)
        await interaction.response.edit_message(embed=embed, view=None)


@app_commands.command(name="move", description="Move a unit to another world")
@app_commands.describe(
    faction="Faction owning the unit",
    unit_id="Unit ID or name to move",
    destination="World to move to",
    use_lanes="Route through faction lanes when faster than the direct route"
)
@require_access_level(0)
@ephemeral_capable('faction')
async def unit_move(
    interaction: discord.Interaction,
    faction: str,
    unit_id: str,
    destination: str,
    use_lanes: bool = False
):
    await defer_response(interaction)

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data.color)

    r_unit_data = await require_unit(unit_id, faction_data.id)
    if not r_unit_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_unit_data.error))
    unit_data = r_unit_data.data

    r_dest = await require_world(destination)
    if not r_dest.ok: return await interaction.followup.send(embed=error_embed("Error", r_dest.error))
    dest_data = r_dest.data

    if dest_data['id'] == unit_data['position']:
        await interaction.followup.send(embed=error_embed("Error", "Unit is already at that location."))
        return

    if static_cache.get_system_id(unit_data['position']) != static_cache.get_system_id(dest_data['id']):
        unit_name = unit_data['name'] or f"Unit #{unit_data['faction_fleet_number']}"
        from_system = static_cache.get_system_name(unit_data['position'])
        to_system = static_cache.get_system_name(dest_data['id'])
        embed = discord.Embed(
            title="Leaving System",
            description=(
                f"**{unit_name}** is about to leave the **{from_system}** system for the **{to_system}** system.\n\n"
                f"Once it arrives, its CS upkeep will be drawn from your worlds in the {to_system} system. "
                f"If you lack CS there, the unit takes upkeep damage."
            ),
            color=faction_color,
        )
        view = CrossSystemMoveView(interaction.user.id, unit_data, dest_data, faction_data.id, faction_color, use_lanes)
        await interaction.followup.send(embed=embed, view=view)
        return

    embed = await execute_move(unit_data, dest_data, faction_data.id, faction_color, use_lanes)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    unit_move.autocomplete('faction')(faction_autocomplete)
    bot.tree.add_command(unit_move)
