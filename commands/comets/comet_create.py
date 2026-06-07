import discord
from discord import app_commands
from utils.checks import require_access_level
from utils.embeds import error_embed, success_embed
from services.comet_service import create_comet
from services.user_service import check_user_exists, create_user


@app_commands.command(name="create", description="Discover and register a new comet")
@app_commands.describe(
    name="Name of the comet",
    message="A message to accompany the comet"
)
@require_access_level(0)
async def comet_create(
    interaction: discord.Interaction,
    name: str,
    message: str
):
    await interaction.response.defer()

    user_id = interaction.user.id
    if not await check_user_exists(user_id):
        await create_user(user_id)

    try:
        comet = await create_comet(name, message, user_id)
    except ValueError as e:
        await interaction.followup.send(embed=error_embed("Error", str(e)))
        return

    embed = success_embed(
        f"**{comet['name']}** has been recorded in the star charts.\n\n"
        f"*{comet['message']}*",
        "Comet Discovered",
    )
    embed.add_field(name="Discoverer", value=interaction.user.display_name, inline=True)
    await interaction.followup.send(embed=embed)


async def setup(bot):
    pass
