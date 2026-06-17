import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.war_service import join_war as join_war_service
from services.validation_service import require_faction


@app_commands.command(name="join", description="Join an existing war")
@app_commands.describe(war_id="ID of the war to join", side="Which side to join (any label)", faction="Your faction name")
@require_access_level(0)
async def join_war(interaction: discord.Interaction, war_id: int, side: str, faction: str):
    await interaction.response.defer()

    side = side.strip().upper()
    if not side:
        await interaction.followup.send(embed=error_embed("Error", "Side cannot be empty."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data['color'])

    try:
        result = await join_war_service(war_id, faction_data['id'], side)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    war_data = result['war']
    stats = result['stats']
    stats_text = "\n".join(f"**Side {s['side']}:** {', '.join(s['faction_names'])}" for s in stats) if stats else "No other participants."
    embed = success_embed(
        title="Joined War",
        description=f"**{faction_data['display_name']}** has joined **{war_data['name']}**!\n"
                    f"**War ID:** {war_id}\n**Side:** {side}\n**Active Battles:** {result['battle_count']}\n\n"
                    f"**Current Participants:**\n{stats_text}"
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(join_war)
