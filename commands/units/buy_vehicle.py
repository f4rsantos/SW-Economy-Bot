import math
import discord
from discord import app_commands
from datetime import datetime, timezone, timedelta
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.fleet_service import buy_vehicle, get_factory_info
from services.vehicle_service import get_vehicle_definition, build_days
from services.validation_service import require_faction, require_unit, require_vehicle, require_world


@app_commands.command(name="buy", description="Order construction of vehicles")
@app_commands.describe(
    faction="Faction to buy for",
    unit_id="Unit ID or name to receive vehicles",
    vehicle_id="Vehicle display ID or name",
    world="World where vehicles will be built",
    amount="Number of vehicles to build",
    source_faction="Source faction name or ID (required if buying from another faction)"
)
@require_access_level(0)
async def buy_vehicle_cmd(
    interaction: discord.Interaction,
    faction: str,
    unit_id: str,
    vehicle_id: str,
    world: str,
    amount: int,
    source_faction: str = None
):
    await interaction.response.defer()

    if amount < 1 or amount > 10000:
        await interaction.followup.send(embed=error_embed("Error", "Amount must be between 1 and 10,000."))
        return

    r_user_faction = await require_faction(faction)
    if not r_user_faction.ok: return await interaction.followup.send(embed=error_embed("Error", r_user_faction.error))
    user_faction = r_user_faction.data

    faction_color = hex_to_int(user_faction['color'])

    r_unit_data = await require_unit(unit_id, user_faction['id'])
    if not r_unit_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_unit_data.error))
    unit_data = r_unit_data.data

    r_world = await require_world(world)
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
    world_data = r_world.data

    if unit_data['position'] != world_data['id']:
        return await interaction.followup.send(embed=error_embed("Error", f"Fleet must be on {world_data['name']} to build vehicles there. Fleet is on {unit_data['world_name']}."))

    if source_faction:
        r_src_faction = await require_faction(source_faction)
        if not r_src_faction.ok: return await interaction.followup.send(embed=error_embed("Error", r_src_faction.error))
        target_faction_id = r_src_faction.data['id']
    else:
        target_faction_id = user_faction['id']

    r_vehicle_data = await require_vehicle(vehicle_id, target_faction_id)
    if not r_vehicle_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_vehicle_data.error))
    vehicle_data = r_vehicle_data.data

    vehicle_def = await get_vehicle_definition(vehicle_data['id'])
    if not vehicle_def:
        await interaction.followup.send(embed=error_embed("Error", "Vehicle definition not found."))
        return
    vehicle_length = vehicle_def['length']
    costs = [{'name': k, 'amount': v} for k, v in vehicle_def['costs'].items()]
    if not costs:
        await interaction.followup.send(embed=error_embed("Error", "Vehicle has no cost defined."))
        return

    is_missile = (vehicle_def.get('type_name') or '').lower() == 'missile'
    total_factory_space = vehicle_length * amount

    base_days = build_days(vehicle_length)

    if is_missile:
        total_capacity = 0
        shortfall_multiplier = 0
    else:
        is_large = vehicle_length > 1000
        total_capacity, used_space = await get_factory_info(world_data['id'], user_faction['id'], is_large)
        available_space = total_capacity - used_space

        if total_factory_space > available_space:
            if is_large:
                if total_capacity == 0:
                    await interaction.followup.send(embed=error_embed("No Mega Factory", f"This vehicle is {vehicle_length}m — you need a Mega Factory to build vehicles > 1000m."))
                    return
                if available_space <= 0:
                    await interaction.followup.send(embed=error_embed("Insufficient Mega Factory Capacity",
                        f"**Needed:** {total_factory_space:,.0f}m\n**Available:** {available_space:,.0f}m\n**Total Capacity:** {total_capacity:,.0f}m\nAll factory space is currently occupied."))
                    return
                shortfall_multiplier = math.ceil(total_factory_space / total_capacity)
            else:
                await interaction.followup.send(embed=error_embed("Insufficient Factory Capacity",
                    f"**Needed:** {total_factory_space:,.0f}m\n**Available:** {available_space:,.0f}m\n**Total Capacity:** {total_capacity:,.0f}m"))
                return
        else:
            shortfall_multiplier = 1

    total_days = 0 if is_missile else base_days * shortfall_multiplier
    completion = datetime.now(timezone.utc) + timedelta(days=total_days)
    costs_list = [{"name": c['name'], "amount": c['amount']} for c in costs]

    try:
        order_id = await buy_vehicle(
            user_faction['id'], world_data['id'], unit_data['id'],
            vehicle_data['id'], amount, int(total_factory_space), completion, costs_list
        )
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    unit_name = unit_data['name'] or f"Unit #{unit_data['faction_fleet_number']}"
    cost_summary = ", ".join(f"{c['amount'] * amount:,} {c['name']}" for c in costs)

    embed = discord.Embed(
        title="Vehicle Construction Ordered",
        description=f"**{amount:,}x {vehicle_data['name']}**",
        color=faction_color
    )
    embed.add_field(name="Order ID",       value=str(order_id),                         inline=True)
    embed.add_field(name="Unit",           value=unit_name,                              inline=True)
    embed.add_field(name="Build Location", value=world_data['name'],                     inline=True)
    embed.add_field(name="Cost",       value=cost_summary,                           inline=False)
    if not is_missile:
        embed.add_field(name="Factory Space", value=f"{total_factory_space:,.0f} / {total_capacity:,.0f}m", inline=True)
        embed.add_field(name="Completion", value=f"<t:{int(completion.timestamp())}:R>", inline=True)
    footer = "Missiles added to unit instantly." if is_missile else f"Vehicles will join the unit when construction completes ({total_days:,.1f} day{'s' if total_days != 1 else ''})"
    embed.set_footer(text=footer)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(buy_vehicle_cmd)
