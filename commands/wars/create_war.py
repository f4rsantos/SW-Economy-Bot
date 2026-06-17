import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.war_service import create_war, get_existing_war_for_faction
from services.validation_service import require_faction


@app_commands.command(name="create", description="Create a new war")
@app_commands.describe(name="Name of the war", side="Which side your faction will be on (any label)", faction="Your faction name")
@require_access_level(0)
async def create_war_cmd(interaction: discord.Interaction, name: str, side: str, faction: str):
    await interaction.response.defer()

    side = side.strip().upper()
    if not side:
        await interaction.followup.send(embed=error_embed("Error", "Side cannot be empty."))
        return

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data['color'])

    existing = await get_existing_war_for_faction(faction_data['id'])
    if existing:
        await interaction.followup.send(embed=error_embed("Warning", f"Your faction is already in **{existing['name']}** (War #{existing['id']}) on side **{existing['side']}**. You can still create a new war."))

    try:
        war_id = await create_war(name, faction_data['id'], side)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(
        title="War Created",
        description=f"**{name}** has been declared!\n**War ID:** {war_id}\n**Started by:** {faction_data['display_name']} (Side {side})\n\nOther factions can join with `/join-war`."
    )
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(create_war_cmd)
