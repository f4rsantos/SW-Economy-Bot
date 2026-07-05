import discord
from discord import app_commands
from datetime import datetime, timezone, timedelta
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return, parse_currency
from utils.faction_utils import hex_to_int
from utils.fleet_utils import get_vehicle_in_fleet
from services.fleet_service import refit_vehicle
from services.vehicle_service import get_vehicle_definition, build_days, compute_refit
from services.validation_service import require_faction, require_unit, require_world


@app_commands.command(name="refit", description="Refit vehicles in a unit to their registered cost")
@app_commands.describe(
    faction="Faction that owns the unit",
    unit_id="Unit ID or name holding the vehicles",
    vehicle_id="Vehicle display ID or name",
    old_cost="Previous cost of the vehicle (per unit), e.g. '1000 CM, 500 EL'",
    world="World where removed resources are credited and refit occurs",
    amount="Number of vehicles to refit",
    vehicle_faction_origin="Faction that owns the vehicle design (if not the source faction)"
)
@require_access_level(0)
async def refit_cmd(
    interaction: discord.Interaction,
    faction: str,
    unit_id: str,
    old_cost: str,
    world: str,
    amount: int,
    vehicle_id: str,
    vehicle_faction_origin: str = None
):
    await interaction.response.defer()

    if amount < 1:
        await interaction.followup.send(embed=error_embed("Error", "Amount must be at least 1."))
        return

    r_user_faction = await require_faction(faction)
    if not r_user_faction.ok: return await interaction.followup.send(embed=error_embed("Error", r_user_faction.error))
    user_faction = r_user_faction.data
    faction_color = hex_to_int(user_faction['color'])

    r_unit = await require_unit(unit_id, user_faction['id'])
    if not r_unit.ok: return await interaction.followup.send(embed=error_embed("Error", r_unit.error))
    unit_data = r_unit.data

    r_world = await require_world(world)
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
    world_data = r_world.data

    origin_faction_id = None
    if vehicle_faction_origin:
        r_origin = await require_faction(vehicle_faction_origin)
        if not r_origin.ok: return await interaction.followup.send(embed=error_embed("Error", r_origin.error))
        origin_faction_id = r_origin.data['id']

    target_vehicle = await get_vehicle_in_fleet(vehicle_id, unit_data['id'], origin_faction_id)
    if not target_vehicle:
        await interaction.followup.send(embed=error_embed("Error", f"Vehicle '{vehicle_id}' not found in unit."))
        return

    vehicle_def = await get_vehicle_definition(target_vehicle['id'])
    if not vehicle_def:
        await interaction.followup.send(embed=error_embed("Error", "Vehicle definition not found."))
        return

    try:
        parsed_old = parse_currency(old_cost)
    except Exception as e:
        await interaction.followup.send(embed=error_embed("Error", f"Invalid old cost format: {e}"))
        return

    new_costs = dict(vehicle_def['costs'])
    canonical = {k.lower(): k for k in new_costs}
    old_costs = {}
    for c in parsed_old:
        name = canonical.get(c['resource'].lower(), c['resource'])
        old_costs[name] = old_costs.get(name, 0) + c['amount']

    cost_deltas, ratio = compute_refit(new_costs, old_costs)

    refit_days = build_days(vehicle_def['length']) * 0.75 * ratio
    completion = datetime.now(timezone.utc) + timedelta(days=refit_days)
    factory_space = int(vehicle_def['length'] * amount)

    try:
        order_id = await refit_vehicle(
            user_faction['id'], unit_data['id'], target_vehicle['id'], amount,
            world_data['id'], factory_space, completion, cost_deltas
        )
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    charged = [f"{handle_return(d['amount'] * amount)} {d['name']}" for d in cost_deltas if d['amount'] > 0]
    credited = [f"{handle_return(-d['amount'] * amount)} {d['name']}" for d in cost_deltas if d['amount'] < 0]

    unit_name = unit_data['name'] or f"Unit #{unit_data['faction_fleet_number']}"
    embed = success_embed(
        "Vehicles Refit Ordered",
        f"**{amount:,}x {target_vehicle['name']}** in **{unit_name}** are being refit on **{world_data['name']}**."
    )
    embed.color = faction_color
    embed.add_field(name="Order ID", value=str(order_id), inline=True)
    embed.add_field(name="Charged", value=", ".join(charged) if charged else "None", inline=False)
    embed.add_field(name="Credited", value=", ".join(credited) if credited else "None", inline=False)
    embed.add_field(name="Completion", value=f"<t:{int(completion.timestamp())}:R>", inline=True)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
