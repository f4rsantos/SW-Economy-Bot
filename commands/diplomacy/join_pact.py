import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.pact_service import get_pact, join_pact as join_pact_service
from services.validation_service import require_faction


@app_commands.command(name="join", description="Join an existing diplomatic pact")
@app_commands.describe(faction="Faction name", pact_id="Pact ID to join")
@require_access_level(0)
async def join_pact(interaction: discord.Interaction, faction: str, pact_id: int):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_id = faction_data['id']
    faction_color = hex_to_int(faction_data['color'])

    pact_data = await get_pact(pact_id)
    if not pact_data:
        await interaction.followup.send(embed=error_embed("Error", "Pact not found."))
        return

    try:
        result = await join_pact_service(pact_id, faction_id, pact_data)
    except ValueError as e:
        msg = str(e)
        title = "Leader Cannot Afford" if "cannot afford" in msg.lower() else "Error"
        await interaction.followup.send(embed=error_embed(title, msg))
        return

    embed = success_embed(
        title="Joined Pact",
        description=f"**{faction_data['display_name']}** has joined **{pact_data['name']}** ({pact_data['pact_type']}).\n\n"
                    f"**Leader:** {pact_data['leader_name']}\n"
                    f"**Total Members:** {result['member_count']}"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(join_pact)
