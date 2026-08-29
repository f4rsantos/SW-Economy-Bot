# Copyright (c) 2026 f4rsantos. All rights reserved.
# Unauthorized copying, modification, or distribution of this file,
# via any medium, is strictly prohibited without explicit written
# permission from the copyright holder. Contact: f4rsantos@gmail.com

from typing import Optional
from datetime import timedelta
import discord
from discord import app_commands
from utils.embeds import error_embed
from utils.autocomplete import faction_autocomplete
from services.travel_time_service import calculate_travel_time, format_travel_time
from services.validation_service import require_faction, require_world
from services import port_service
from utils.route_map import build_route_map_file, ROUTE_MAP_URL


@app_commands.command(name="travel-time", description="Calculate travel time between two worlds")
@app_commands.describe(
    origin="Starting world (e.g. Earth)",
    destination="Destination world (e.g. Mars)",
    faction="Your faction, required to consider lanes",
    use_lanes="Route through faction lanes when faster than the direct route",
)
async def travel_time(
    interaction: discord.Interaction,
    origin: str,
    destination: str,
    faction: Optional[str] = None,
    use_lanes: bool = False,
):
    await interaction.response.defer()

    route_info = None
    try:
        if use_lanes and faction:
            r_faction = await require_faction(faction)
            if not r_faction.ok:
                await interaction.followup.send(embed=error_embed("Navigation Error", r_faction.error))
                return
            r_origin = await require_world(origin)
            if not r_origin.ok:
                await interaction.followup.send(embed=error_embed("Navigation Error", r_origin.error))
                return
            r_dest = await require_world(destination)
            if not r_dest.ok:
                await interaction.followup.send(embed=error_embed("Navigation Error", r_dest.error))
                return

            route_info = await port_service.calculate_best_route(
                r_origin.data['id'], r_origin.data['name'], r_dest.data['id'], r_dest.data['name'],
                r_faction.data.id, port_service.TRAFFIC_UNITS,
            )
            time_str = await format_travel_time(route_info['duration'])
        else:
            time_delta = await calculate_travel_time(origin, destination)
            time_str = await format_travel_time(time_delta)
    except Exception as e:
        await interaction.followup.send(embed=error_embed("Navigation Error", f"Failed to calculate course: {str(e)}"))
        return

    embed = discord.Embed(
        title="Travel Time Simulation",
        description=f"Calculating trajectory from **{origin}** to **{destination}**...",
        color=discord.Color.blue()
    )
    embed.add_field(name="Estimated Travel Time", value=f"**{time_str}**", inline=False)

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

    route_world_names = [origin, destination]
    if route_info and route_info['used_lanes']:
        from services.map_service import get_worlds_by_ids
        path_worlds = await get_worlds_by_ids(route_info['world_path'])
        path_names_by_id = {w['id']: w['name'] for w in path_worlds}
        route_world_names = [path_names_by_id.get(wid, str(wid)) for wid in route_info['world_path']]

    map_file = await build_route_map_file(origin, destination, route_world_names)
    if map_file is not None:
        embed.set_image(url=ROUTE_MAP_URL)

    embed.set_footer(text="Based on current orbital alignment.")
    if map_file is not None:
        await interaction.followup.send(embed=embed, file=map_file)
    else:
        await interaction.followup.send(embed=embed)


async def setup(bot):
    travel_time.autocomplete('faction')(faction_autocomplete)
    bot.tree.add_command(travel_time)
