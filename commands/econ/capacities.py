import asyncio
import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.building_efficiency_service import calculate_effective_efficiency, get_faction_efficiency_map
from services.validation_service import require_faction, require_world
from services.econ_query_service import (
    get_producible_resource_by_name_upper,
    get_world_capacities_for_resource,
    get_capacity_rows_for_world,
    get_capacity_rows_overall,
    get_factory_capacity,
    get_mega_factory_capacity,
)


@app_commands.command(name="capacities", description="View faction's production capacity")
@app_commands.describe(faction="Faction name", world="World name", resource="Resource name")
@require_access_level(0)
async def capacities(
    interaction: discord.Interaction,
    faction: str,
    world: Optional[str] = None,
    resource: Optional[str] = None
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data['id']
    faction_color = hex_to_int(faction_data['color'])

    if resource:
        res_row = await get_producible_resource_by_name_upper(resource.upper())
        if not res_row:
            await interaction.followup.send(embed=error_embed("Error", f"`{resource}` is not a producible resource."))
            return

        rows = await get_world_capacities_for_resource(faction_id, res_row['id'])

        world_production: dict = {}
        is_refinery = False
        for row in rows:
            if not row['total_buildings'] or row['production'] is None:
                continue
            raw = row['production'] * row['total_buildings']
            amount = (raw * (row['resource_percentage'] or 100)) // 100 if row['percentage_affects'] else raw
            world_production[row['world_name']] = world_production.get(row['world_name'], 0) + amount
            if row['is_refinery']:
                is_refinery = True

        eff = await calculate_effective_efficiency(faction_id, building_type='refinery' if is_refinery else 'extractor', resource_name=res_row['name'])
        embed = discord.Embed(title=f"Capacities ({res_row['name']}): {faction_data['display_name']} per World", color=faction_color)
        sorted_worlds = sorted(world_production.items(), key=lambda x: x[1], reverse=True)
        total = 0
        lines = []
        for wname, prod in sorted_worlds:
            if prod > 0:
                final = int(prod * eff)
                lines.append(f"**{wname}**: {handle_return(final)}")
                total += final
        embed.description = "\n".join(lines) if lines else f"No production buildings for {res_row['name']} on any world."
        if lines:
            embed.set_footer(text=f"Total: {handle_return(total)} | Efficiency: {eff:.0%}")
        await interaction.followup.send(embed=embed)
        return

    factory_capacity = 0
    mega_factory_capacity = 0

    if world:
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
        world_data = r_world.data
        world_id = world_data['id']
        production_data, factory_capacity, mega_factory_capacity, eff_map = await asyncio.gather(
            get_capacity_rows_for_world(faction_id, world_id),
            get_factory_capacity(faction_id, world_id),
            get_mega_factory_capacity(faction_id, world_id),
            get_faction_efficiency_map(faction_id)
        )
        title = f"Capacities - {faction_data['display_name']} on {world_data['name']}"
    else:
        raw_data, factory_capacity, mega_factory_capacity, eff_map = await asyncio.gather(
            get_capacity_rows_overall(faction_id),
            get_factory_capacity(faction_id),
            get_mega_factory_capacity(faction_id),
            get_faction_efficiency_map(faction_id)
        )
        resource_map: dict = {}
        for prod in raw_data:
            r_name = prod['name']
            if r_name not in resource_map:
                resource_map[r_name] = {'name': r_name, 'is_refinery': prod['is_refinery'], 'calculated_production': 0}
            if prod['total_buildings'] and prod['total_buildings'] > 0:
                base = prod['production'] * prod['total_buildings']
                amount = (base * (prod['resource_percentage'] or 100)) // 100 if prod['percentage_affects'] else base
                resource_map[r_name]['calculated_production'] += amount
        production_data = list(resource_map.values())
        title = f"Capacities - {faction_data['display_name']} (Overall)"

    embed = success_embed(title=title, description="Theoretical maximum production capacity per cycle\n*(Includes efficiency & specialization modifiers)*")
    embed.color = faction_color
    has_production = False
    for prod in production_data:
        building_type = 'refinery' if prod['is_refinery'] else 'extractor'
        if world:
            if not prod.get('total_buildings') or prod['total_buildings'] <= 0:
                continue
            raw = prod['production'] * prod['total_buildings']
            production_val = (raw * (prod['resource_percentage'] or 100)) // 100 if prod['percentage_affects'] else raw
        else:
            if prod.get('calculated_production', 0) <= 0:
                continue
            production_val = prod['calculated_production']

        eff = eff_map(building_type, prod['name'])
        embed.add_field(name=prod['name'], value=handle_return(int(production_val * eff)), inline=True)
        has_production = True

    if factory_capacity > 0 or mega_factory_capacity > 0:
        factory_eff = await calculate_effective_efficiency(faction_id, building_type='factory')
        if factory_capacity > 0:
            embed.add_field(name="Factory Space", value=f"{int(factory_capacity * factory_eff):,}m", inline=True)
            has_production = True
        if mega_factory_capacity > 0:
            embed.add_field(name="Mega Factory Space", value=f"{int(mega_factory_capacity * factory_eff):,}m", inline=True)
            has_production = True

    if not has_production:
        embed.description = "No production buildings found."

    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(capacities)
