import asyncio
import discord
from discord import app_commands
from typing import Optional
from datetime import datetime, timezone
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return, parse_currency
from utils.faction_utils import hex_to_int
from services.treasury_service import find_best_worlds_for_multiple_resources
from services.map_service import get_world, get_world_by_id
from services.econ_query_service import get_resource_ids_by_names, get_global_resource_amount
from services.validation_service import require_faction, require_world
from services.transfer_service import (
    execute_er_transfer,
    execute_physical_transfer,
    get_world_for_faction,
    has_world_presence,
    ensure_world_presence,
    get_local_resource_amount,
    intercept_transfer,
)
from services.blockade_service import get_blockading_fleet_for_world
from services.fleet_service import get_fleet_by_identifier


@app_commands.command(name="transfer", description="Transfer resources between factions")
@app_commands.describe(
    from_faction="Sending faction name",
    to_faction="Receiving faction name",
    amount="Amount in format: 1000 ER, 500 CM, etc. (comma separated)",
    to_world="Destination world name (optional for ER transfers)",
    from_world="Source world name (optional)",
    escort_fleet="Fleet (faction fleet number) escorting this transfer"
)
@require_access_level(0)
async def transfer(
    interaction: discord.Interaction,
    from_faction: str,
    to_faction: str,
    amount: str,
    to_world: Optional[str] = None,
    from_world: Optional[str] = None,
    escort_fleet: Optional[str] = None
):
    await interaction.response.defer()

    r_from_faction_data, r_to_faction_data = await asyncio.gather(
        require_faction(from_faction),
        require_faction(to_faction)
    )
    if not r_from_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_from_faction_data.error))
    from_faction_data = r_from_faction_data.data
    if not r_to_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_to_faction_data.error))
    to_faction_data = r_to_faction_data.data

    from_faction_id = from_faction_data['id']
    to_faction_id = to_faction_data['id']
    from_faction_color = hex_to_int(from_faction_data['color'])

    try:
        transfers = parse_currency(amount)
    except Exception as e:
        await interaction.followup.send(embed=error_embed("Error", f"Invalid amount format: {e}"))
        return

    resource_names = [t['resource'] for t in transfers]
    resource_map = await get_resource_ids_by_names(resource_names)
    if len(resource_map) != len(resource_names):
        await interaction.followup.send(embed=error_embed("Error", "One or more invalid resource types."))
        return

    canonical = {name.lower(): name for name in resource_map}
    for t in transfers:
        t['resource'] = canonical.get(t['resource'].lower(), t['resource'])

    if from_faction_id != to_faction_id:
        non_transferable = sorted({t['resource'] for t in transfers if not resource_map[t['resource']]['is_transferable']})
        if non_transferable:
            await interaction.followup.send(embed=error_embed("Error", f"{', '.join(non_transferable)} can only be transferred within your own faction."))
            return

    is_global = all(t['resource'] == 'ER' for t in transfers)

    to_world_data = None
    to_world_id = None
    if to_world:
        r_to_world = await require_world(to_world)
        if not r_to_world.ok:
            await interaction.followup.send(embed=error_embed("Error", r_to_world.error))
            return
        to_world_data = r_to_world.data
        to_world_id = to_world_data['id']
    elif is_global:
        to_world_data = await get_world_for_faction(to_faction_id)
        if not to_world_data:
            await interaction.followup.send(embed=error_embed("Error", "Destination faction has no colonized worlds."))
            return
        to_world_id = to_world_data['id']
    else:
        await interaction.followup.send(embed=error_embed("Error", "You must specify a destination world for physical resource transfers."))
        return

    if not await has_world_presence(to_world_id, to_faction_id):
        if from_faction_id == to_faction_id:
            await ensure_world_presence(to_world_id, to_faction_id)
        else:
            await interaction.followup.send(embed=error_embed("Error", f"{to_faction_data['display_name']} has no presence on {to_world_data['name']}."))
            return

    current_time = datetime.now(timezone.utc)

    if is_global:
        er_id = resource_map['ER']['id']
        total_amount = sum(t['amount'] for t in transfers)

        current = await get_global_resource_amount(from_faction_id, er_id)
        if current < total_amount:
            await interaction.followup.send(embed=error_embed("Error", f"Insufficient funds. Need {handle_return(total_amount)} ER, have {handle_return(current)} ER."))
            return

        if from_world:
            fw = await get_world(from_world)
            from_world_id = fw['id'] if fw else to_world_id
        else:
            fw = await get_world_for_faction(from_faction_id)
            from_world_id = fw['id'] if fw else to_world_id

        await execute_er_transfer(from_faction_id, to_faction_id, from_world_id, to_world_id, er_id, total_amount, current_time)

        embed = success_embed(
            title="Global Transfer Complete",
            description=f"**{from_faction_data['display_name']}** transferred **{handle_return(total_amount)} ER** to **{to_faction_data['display_name']}**.\n\n"
                        f"**Source:** Global Treasury\n"
                        f"**Destination:** Global Treasury (ref: {to_world_data['name']})\n"
                        f"**Status:** Instant Transfer"
        )
        embed.color = from_faction_color
        await interaction.followup.send(embed=embed)
        return

    if from_world:
        r_from_world = await require_world(from_world)
        if not r_from_world.ok:
            await interaction.followup.send(embed=error_embed("Error", r_from_world.error))
            return
        from_world_data = r_from_world.data
        from_world_id = from_world_data['id']
    else:
        resource_list = [{'resource_id': resource_map[t['resource']]['id'], 'amount': t['amount']} for t in transfers]
        from_world_id = await find_best_worlds_for_multiple_resources(from_faction_id, resource_list)
        if not from_world_id:
            await interaction.followup.send(embed=error_embed("Error", "No single world has all required resources. Please specify a source world."))
            return
        from_world_data = await get_world_by_id(from_world_id)

    if not await has_world_presence(from_world_id, from_faction_id):
        await interaction.followup.send(embed=error_embed("Error", f"{from_faction_data['display_name']} has no presence on {from_world_data['name']}."))
        return

    for t in transfers:
        have = await get_local_resource_amount(from_world_id, from_faction_id, resource_map[t['resource']]['id'])
        if have < t['amount']:
            await interaction.followup.send(embed=error_embed("Error", f"Not enough {t['resource']} at {from_world_data['name']}. Need {handle_return(t['amount'])}, have {handle_return(have)}."))
            return

    escort_fleet_id = None
    if escort_fleet:
        fleet_data = await get_fleet_by_identifier(escort_fleet, from_faction_id)
        if not fleet_data:
            await interaction.followup.send(embed=error_embed("Error", f"Fleet '{escort_fleet}' not found."))
            return
        if fleet_data['position'] != from_world_id:
            await interaction.followup.send(embed=error_embed("Error", f"Escort fleet must be at {from_world_data['name']} to escort this transfer."))
            return
        if fleet_data['status_name'].lower() not in ('idle', 'defence', 'defense', 'patrol', 'blockading', 'ftl supply'):
            await interaction.followup.send(embed=error_embed("Error", f"Escort fleet cannot travel while status is {fleet_data['status_name']}."))
            return
        escort_fleet_id = fleet_data['id']

    try:
        result = await execute_physical_transfer(
            from_faction_id, to_faction_id,
            from_world_id, to_world_id,
            from_world_data['name'], to_world_data['name'],
            transfers, resource_map, current_time, escort_fleet_id
        )
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    intercepting_fleet_id = None
    if from_world_id != to_world_id:
        interception_world_id = from_world_id
        intercepting_fleet_id = await get_blockading_fleet_for_world(from_world_id, from_faction_id)
        if intercepting_fleet_id is None:
            interception_world_id = to_world_id
            intercepting_fleet_id = await get_blockading_fleet_for_world(to_world_id, to_faction_id)
        if intercepting_fleet_id is not None:
            try:
                await intercept_transfer(result['transfer_id'], intercepting_fleet_id, interception_world_id)
            except ValueError:
                intercepting_fleet_id = None

    transfer_str = ", ".join(f"{handle_return(t['amount'])} {t['resource']}" for t in transfers)
    if intercepting_fleet_id is not None:
        embed = success_embed(
            title="Transfer Intercepted",
            description=f"**{from_faction_data['display_name']}** attempted to transfer {transfer_str} from **{from_world_data['name']}** to **{to_faction_data['display_name']}** at **{to_world_data['name']}**, but it was intercepted by a blockade.\n\n"
                        f"**Transfer ID:** {result['transfer_id']}"
        )
    else:
        escort_line = f"**Escort:** {escort_fleet}\n" if escort_fleet_id is not None else ""
        embed = success_embed(
            title="Transfer In Transit",
            description=f"**{from_faction_data['display_name']}** is transferring {transfer_str} from **{from_world_data['name']}** to **{to_faction_data['display_name']}** at **{to_world_data['name']}**\n\n"
                        f"**Travel Time:** {result['travel_str']}\n"
                        f"**Arrival:** <t:{int(result['arrival_time'].timestamp())}:F>\n"
                        f"{escort_line}"
                        f"**Transfer ID:** {result['transfer_id']}"
        )
    embed.color = from_faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(transfer)
