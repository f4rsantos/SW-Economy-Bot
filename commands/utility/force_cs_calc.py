import logging
import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from services.utility_service import recalc_fleet_cs_for_faction
from services.validation_service import require_faction

logger = logging.getLogger(__name__)


@app_commands.command(name="force-cs-calc", description="Recalculate CS cost for all fleets of a faction (Level 10 only)")
@app_commands.describe(faction="Faction name to recalculate fleet CS for")
@require_access_level(9)
async def force_cs_calc(interaction: discord.Interaction, faction: str):
    await interaction.response.defer(ephemeral=True)

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error), ephemeral=True)
    faction_data = r_faction_data.data

    faction_id = faction_data['id']
    faction_name = faction_data.get('display_name') or faction_data['name']

    try:
        updated = await recalc_fleet_cs_for_faction(faction_id)
        logger.info(f"[FORCE-CS-CALC] {interaction.user} recalculated CS for {faction_name}: {updated} fleet(s) updated")
        await interaction.followup.send(embed=success_embed("CS Recalculated", f"Recalculated `total_cs` for **{updated}** fleet(s) in **{faction_name}**."), ephemeral=True)
    except Exception as e:
        logger.exception(f"[FORCE-CS-CALC] Error for {faction_name}: {e}")
        await interaction.followup.send(embed=error_embed("Error", f"CS recalculation failed for **{faction_name}**:\n```{e}```"), ephemeral=True)


async def setup(bot):
    bot.tree.add_command(force_cs_calc)
