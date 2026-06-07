import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.currency import handle_return, parse_currency
from utils.faction_utils import hex_to_int
from services.transfer_service import deduct_resources, get_resource_name_to_id
from services.validation_service import require_faction, require_world

LOCAL_RESOURCES = {'CM', 'EL', 'CS', 'U-CM', 'U-EL', 'U-CS', 'Population'}


@app_commands.command(name="buy", description="Buy unregistered items")
@app_commands.describe(
    faction="Faction name",
    items="Description of items being bought",
    cost="Cost in format: 1000 ER, 500 CM, 100 Military, etc. (comma separated)",
    quantity="Multiply all costs by this cost (default: 1)",
    world="World name for local resources (CM, EL, CS, Population, etc.)"
)
@require_access_level(0)
async def buy(
    interaction: discord.Interaction,
    faction: str,
    items: str,
    cost: str,
    quantity: Optional[int] = 1,
    world: Optional[str] = None
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error), ephemeral=True)
    faction_data = r_faction_data.data

    faction_id = faction_data['id']
    faction_color = hex_to_int(faction_data['color'])

    if quantity is not None and quantity < 1:
        await interaction.followup.send(embed=error_embed("Error", "Quantity must be at least 1."), ephemeral=True)
        return

    try:
        costs = parse_currency(cost)
    except Exception as e:
        await interaction.followup.send(embed=error_embed("Error", f"Invalid cost format: {e}"), ephemeral=True)
        return

    if quantity and quantity > 1:
        costs = [{'resource': c['resource'], 'amount': c['amount'] * quantity} for c in costs]

    needs_world = any(c['resource'] in LOCAL_RESOURCES for c in costs)
    if needs_world and not world:
        await interaction.followup.send(
            embed=error_embed("Error", "World name is required for local resources (CM, EL, CS, Population, etc.)."),
            ephemeral=True
        )
        return

    world_id = None
    if world:
        r_world = await require_world(world)
        if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error), ephemeral=True)
        world_id = r_world.data['id']

    resources_dict = {c['resource']: c['amount'] for c in costs}
    resource_names = list(resources_dict.keys())
    resource_map = await get_resource_name_to_id(resource_names)
    if len(resource_map) != len(resource_names):
        await interaction.followup.send(embed=error_embed("Error", "One or more invalid resource types."), ephemeral=True)
        return

    try:
        await deduct_resources(faction_id, world_id, resources_dict)
    except ValueError as e:
        msg = str(e)
        if 'INSUFFICIENT' in msg:
            resource = msg.split(':')[1].strip() if ':' in msg else 'resources'
            await interaction.followup.send(embed=error_embed("Error", f"Not enough {resource}."), ephemeral=True)
        else:
            await interaction.followup.send(embed=error_embed("Error", msg), ephemeral=True)
        return

    cost_str = ", ".join([f"{handle_return(c['amount'])} {c['resource']}" for c in costs])
    embed = success_embed(
        title="Purchase Complete",
        description=f"**{faction_data['display_name']}** has bought {items} for {cost_str}"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(buy)
