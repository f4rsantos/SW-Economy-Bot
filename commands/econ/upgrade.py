import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return
from utils.faction_utils import hex_to_int
from services.transfer_service import upgrade_buildings
from services.building_service import get_building, get_building_base_costs, get_building_cap_info, calculate_upgrade_cost, check_building_cap
from services.validation_service import require_faction, require_world


@app_commands.command(name="upgrade", description="Upgrade buildings to a higher level")
@app_commands.describe(
    faction="Faction name",
    building_id="Building type ID",
    world="World name",
    amount="Number of buildings to upgrade",
    source_level="Current level of buildings (1-9)",
    target_level="Level to upgrade to (2-10)"
)
@require_access_level(0)
async def upgrade(
    interaction: discord.Interaction,
    faction: str,
    building_id: int,
    world: str,
    amount: int,
    source_level: int,
    target_level: int
):
    await interaction.response.defer()

    if amount < 1:
        await interaction.followup.send(embed=error_embed("Error", "Amount must be at least 1."))
        return
    if not (1 <= source_level <= 9):
        await interaction.followup.send(embed=error_embed("Error", "Source level must be between 1 and 9."))
        return
    if not (2 <= target_level <= 10):
        await interaction.followup.send(embed=error_embed("Error", "Target level must be between 2 and 10."))
        return
    if target_level <= source_level:
        await interaction.followup.send(embed=error_embed("Error", f"Target level ({target_level}) must be higher than source level ({source_level})."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data['color'])

    building, r_world, cap_info = await asyncio.gather(
        get_building(building_id),
        require_world(world),
        get_building_cap_info(faction_data['id'], faction_data['is_company'])
    )
    if not building:
        await interaction.followup.send(embed=error_embed("Error", "Building not found."))
        return
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error))
    world_data = r_world.data
    current_weighted = cap_info['building_count']
    building_cap = cap_info['building_cap']
    delta = amount * (target_level - source_level)
    try:
        check_building_cap(current_weighted, delta, building_cap)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    base_costs = await get_building_base_costs(building_id)
    costs = calculate_upgrade_cost(base_costs, building_id, amount, source_level, target_level)

    try:
        await upgrade_buildings(
            faction_data['id'], world_data['id'], building_id,
            amount, source_level, target_level, costs
        )
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    cost_str = ", ".join([f"{handle_return(v)} {k}" for k, v in costs.items()])
    embed = success_embed(
        title="Buildings Upgraded",
        description=f"**{faction_data['display_name']}** upgraded {amount}× **{building['name']}** on **{world_data['name']}** "
                    f"from level {source_level} → {target_level} for {cost_str}"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(upgrade)
