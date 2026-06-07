import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.pact_service import get_pact_type, get_pact_type_names, create_pact as create_pact_service
from services.validation_service import require_faction


@app_commands.command(name="create", description="Create a diplomatic pact")
@app_commands.describe(faction="Faction name (will be pact leader)", pact_name="Name of the pact", pact_type="Type of pact")
@require_access_level(0)
async def create_pact(interaction: discord.Interaction, faction: str, pact_name: str, pact_type: str):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data['id']
    faction_color = hex_to_int(faction_data['color'])

    pact_type_data = await get_pact_type(pact_type)
    if not pact_type_data:
        valid_types = ", ".join(await get_pact_type_names())
        await interaction.followup.send(embed=error_embed("Error", f"Invalid pact type. Valid types: {valid_types}"))
        return

    try:
        result = await create_pact_service(pact_name, pact_type_data['id'], faction_id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Negative Influence Income", str(e)))
        return

    pact_id = result['pact_id']

    influence_cost = pact_type_data['influence_cost'] or 0
    embed = success_embed(
        title="Pact Created",
        description=f"**{faction_data['display_name']}** has created the **{pact_name}** ({pact_type}).\n\n"
                    f"**Pact ID:** {pact_id}\n"
                    f"**Influence Cost:** {influence_cost} per additional member\n"
                    f"**Leader:** {faction_data['display_name']}\n\n"
                    f"Other factions can join with `/join-pact {pact_id}`"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(create_pact)
