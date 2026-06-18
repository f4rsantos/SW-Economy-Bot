import asyncio
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from utils.currency import handle_return
from services.conquest_service import conquer_hexes
from services.war_service import are_factions_at_war
from services.validation_service import require_faction, require_world


@app_commands.command(name="conquer", description="Conquer hexes from an enemy faction on a world")
@app_commands.describe(
    my_faction="Your faction name",
    target_faction="Faction to conquer hexes from",
    world="World name",
    hexes="Number of hexes to conquer",
    no_resources="Skip resource/ER rewards and the war requirement, move only population",
)
@require_access_level(0)
async def conquer(interaction: discord.Interaction, my_faction: str, target_faction: str, world: str, hexes: int, no_resources: bool = False):
    await interaction.response.defer()

    r_my_faction, r_target_faction, r_world = await asyncio.gather(
        require_faction(my_faction), require_faction(target_faction), require_world(world)
    )
    if not r_my_faction.ok: return await interaction.followup.send(embed=error_embed("Error", r_my_faction.error), ephemeral=True)
    if not r_target_faction.ok: return await interaction.followup.send(embed=error_embed("Error", r_target_faction.error), ephemeral=True)
    if not r_world.ok: return await interaction.followup.send(embed=error_embed("Error", r_world.error), ephemeral=True)

    my_faction_data = r_my_faction.data
    target_faction_data = r_target_faction.data
    world_data = r_world.data

    if my_faction_data['id'] == target_faction_data['id']:
        await interaction.followup.send(embed=error_embed("Error", "Cannot conquer your own faction."), ephemeral=True)
        return

    if hexes <= 0:
        await interaction.followup.send(embed=error_embed("Error", "Must conquer at least 1 hex."), ephemeral=True)
        return

    if not no_resources:
        at_war = await are_factions_at_war(my_faction_data['id'], target_faction_data['id'])
        if not at_war:
            await interaction.followup.send(embed=error_embed("Error", "Factions must be facing each other in an active war to conquer with rewards. Use no-resources mode otherwise."), ephemeral=True)
            return

    try:
        result = await conquer_hexes(my_faction_data['id'], target_faction_data['id'], world_data['id'], hexes, not no_resources)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)), ephemeral=True)
        return

    faction_color = hex_to_int(my_faction_data['color'])
    lines = [f"**{my_faction_data['display_name']}** conquered **{hexes}** hex(es) from **{target_faction_data['display_name']}** on **{world_data['name']}**."]
    if result['population_moved'] > 0:
        lines.append(f"**Population Moved:** {handle_return(result['population_moved'])}")
    if result['cm_granted'] > 0:
        lines.append(f"**CM Granted:** {handle_return(result['cm_granted'])}")
    if result['el_granted'] > 0:
        lines.append(f"**EL Granted:** {handle_return(result['el_granted'])}")
    if result['cs_granted'] > 0:
        lines.append(f"**CS Granted:** {handle_return(result['cs_granted'])}")
    if result['er_granted'] > 0:
        lines.append(f"**ER Granted:** {handle_return(result['er_granted'])}")
    lines.append(f"**Influence Spent:** {handle_return(result['influence_cost'])}")
    if result['resilience_bonus'] > 0:
        lines.append(f"**{target_faction_data['display_name']}** gains **Resilience** (+{result['resilience_bonus'] * 100:.1f}% Efficiency) through the next income cycle.")

    embed = success_embed(title="Conquest", description="\n".join(lines))
    embed.color = faction_color
    await interaction.followup.send(embed=embed)
