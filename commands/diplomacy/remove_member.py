import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import success_embed, error_embed
from utils.faction_utils import hex_to_int
from services.pact_service import remove_pact_member
from services.validation_service import require_faction


@app_commands.command(name="remove-member", description="Remove member from pact (leader only)")
@app_commands.describe(pact_id="Pact ID", member_faction="Faction name to remove", faction="Your faction name (Pact Leader)")
@require_access_level(0)
async def remove_member(interaction: discord.Interaction, pact_id: int, member_faction: str, faction: str):
    await interaction.response.defer()

    r_user_faction = await require_faction(faction)
    if not r_user_faction.ok: return await interaction.followup.send(embed=error_embed("Error", r_user_faction.error))
    user_faction = r_user_faction.data

    faction_color = hex_to_int(user_faction['color'])

    r_faction_data = await require_faction(member_faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    try:
        result = await remove_pact_member(pact_id, user_faction['id'], faction_data['id'])
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(title="Member Removed", description=f"**{faction_data['display_name']}** has been removed from **{result['name']}** ({result['pact_type']}).")
    embed.color = faction_color
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(remove_member)
