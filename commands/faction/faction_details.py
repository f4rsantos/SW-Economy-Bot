import discord
from discord import app_commands
from typing import Optional
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import get_faction_by_id, hex_to_int
from services.user_service import get_user_access_level
from services.faction_service import update_faction_details, get_faction_row_by_id
from services.validation_service import require_faction, require_world


async def _can_manage_faction(user_id: int, faction_id: int) -> bool:
    if await get_user_access_level(user_id) >= 4:
        return True
    faction = await get_faction_by_id(faction_id)
    return faction is not None and faction['leader_id'] == user_id


@app_commands.command(name="details", description="Edit faction details")
@app_commands.describe(
    faction="The name of the faction to edit",
    color="Hex color code (e.g., #ff0000)",
    leader_treatment="Leader's title/treatment",
    formal_name="Full formal name of the faction",
    flag="Flag emoji or image URL",
    capital_world="Capital world name or ID (nations only)"
)
@require_access_level(0)
async def faction_details(
    interaction: discord.Interaction,
    faction: str,
    color: Optional[str] = None,
    leader_treatment: Optional[str] = None,
    formal_name: Optional[str] = None,
    flag: Optional[str] = None,
    capital_world: Optional[str] = None
):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data['id']

    if not await _can_manage_faction(interaction.user.id, faction_id):
        await interaction.followup.send(embed=error_embed("Access Denied", "You must be the faction leader or have admin privileges to edit this faction."))
        return

    if not any([color, leader_treatment, formal_name, flag, capital_world]):
        await interaction.followup.send(embed=error_embed("No Changes", "You must provide at least one field to update."))
        return

    if color:
        if not color.startswith("#"):
            color = f"#{color}"
        if len(color) != 7:
            await interaction.followup.send(embed=error_embed("Invalid Color", "Color must be in format #RRGGBB"))
            return

    current = await get_faction_row_by_id(faction_id)
    if not current:
        await interaction.followup.send(embed=error_embed("Error", "Faction not found."))
        return

    capital_world_id = None
    capital_world_name = None
    if capital_world:
        if current.get('faction_type', 0) != 0:
            await interaction.followup.send(embed=error_embed("Error", "Only nations can set a capital world."))
            return
        r_capital = await require_world(capital_world)
        if not r_capital.ok: return await interaction.followup.send(embed=error_embed("Error", r_capital.error))
        capital_world_id = r_capital.data['id']
        capital_world_name = r_capital.data['name']

    updated = await update_faction_details(faction_id, color, leader_treatment, formal_name, flag, capital_world_id)

    embed = success_embed(title="Faction Updated", description=f"**{updated.get('formal_name') or updated['name']}** has been updated")
    embed.color = hex_to_int(updated['color'])

    if color:
        embed.add_field(name="Color", value=f"{current['color']} → {updated['color']}", inline=False)
    if leader_treatment is not None:
        embed.add_field(name="Leader Treatment", value=f"{current['leader'] or 'None'} → {updated['leader'] or 'None'}", inline=False)
    if formal_name:
        embed.add_field(name="Formal Name", value=f"{current['formal_name']} → {updated['formal_name']}", inline=False)
    if flag is not None:
        embed.add_field(name="Flag", value=f"{current['flag'] or 'None'} → {updated['flag'] or 'None'}", inline=False)
    if capital_world_id is not None:
        embed.add_field(name="Capital World", value=capital_world_name, inline=False)

    embed.add_field(name="Updated By", value=interaction.user.mention, inline=False)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
