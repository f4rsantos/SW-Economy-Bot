import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed
from utils.faction_utils import hex_to_int
from services.national_spirit_service import get_national_spirits
from services.validation_service import require_faction


@app_commands.command(name="national-spirits", description="View a faction's active national spirits")
@app_commands.describe(faction="Faction name")
@require_access_level(0)
async def national_spirits(interaction: discord.Interaction, faction: str):
    await interaction.response.defer()

    r_faction_data = await require_faction(faction)
    if not r_faction_data.ok: return await interaction.followup.send(embed=error_embed("Error", r_faction_data.error))
    faction_data = r_faction_data.data

    faction_color = hex_to_int(faction_data['color'])

    spirits = await get_national_spirits(faction_data['id'])

    if not spirits:
        description = "No active national spirits."
        has_persistent = False
    else:
        lines = [f"**{s['display_name']}:** +{s['modifier_value'] * 100:.0f}% {s['effect_type'].title()}" for s in spirits]
        description = "\n".join(lines)
        has_persistent = any(s['expires_at'] is None for s in spirits)

    embed = discord.Embed(
        title=f"National Spirits: {faction_data['display_name']}",
        description=description,
        color=faction_color,
    )
    if has_persistent:
        embed.set_footer(text="Persistent spirits remain active until their condition ends (e.g. end of war); others last until the next income cycle.")
    else:
        embed.set_footer(text="Active spirits last until and including the next income cycle.")
    await interaction.followup.send(embed=embed)


async def setup(bot):
    bot.tree.add_command(national_spirits)
