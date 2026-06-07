import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.pact_service import leave_pact as leave_pact_service
from services.validation_service import require_faction


@app_commands.command(name="leave", description="Leave a diplomatic pact")
@app_commands.describe(faction="Faction name", pact_id="Pact ID to leave")
@require_access_level(0)
async def leave_pact(interaction: discord.Interaction, faction: str, pact_id: int):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data['id']
    faction_color = hex_to_int(faction_data['color'])

    try:
        result = await leave_pact_service(pact_id, faction_id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(
        title="Left Pact",
        description=f"**{faction_data['display_name']}** has left **{result['name']}** ({result['pact_type']}).\n\n**Former Leader:** {result['leader_name']}"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(leave_pact)
